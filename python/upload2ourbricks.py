import oauth2
import urlparse
import sys
import pprint
import json
from poster.encode import multipart_encode
from poster.streaminghttp import register_openers
import urllib2
import time
import getopt
import os

# urls for accessing oauth at the service provider
BASE_OURBRICKS    = 'http://ourbricks.com'
REQUEST_TOKEN_URL = BASE_OURBRICKS + '/oauth-request-token'
ACCESS_TOKEN_URL  = BASE_OURBRICKS + '/oauth-access-token'
AUTHORIZATION_URL = BASE_OURBRICKS + '/oauth-authorize'
UPLOAD_URL        = BASE_OURBRICKS + '/api/upload'
UPLOAD_STATUS_URL = BASE_OURBRICKS + '/api/upload-status'
VIEWER_URL        = BASE_OURBRICKS + '/viewer/'

# key and secret granted by the service provider for this consumer application
CONSUMER_KEY = 'YOUR_CONSUMER_KEY_HERE'
CONSUMER_SECRET = 'YOUR_CONSUMER_SECRET_HERE'

# Register the poster module's streaming http handlers with urllib2
register_openers()

LICENSE_CHOICES = ['CC Attribution','CC Attribution-NonCommercial',
                   'CC Attribution-NonCommercial-NoDerivs','CC0 (Public Domain)',
                   'All Rights Reserved','For Sale']

def printresp(resp, content):
    for header, value in resp.iteritems():
        print '%s: %s' % (header, value)
    print content
    
def exitprint(resp, content):
    printresp(resp, content)
    print "Error code: %s" % resp['status']
    sys.exit(1)

def get_choice(message, choices):
    choice = -1
    while choice < 0 or choice >= len(choices):
        for i, c in enumerate(choices):
            print i, c
        choice = raw_input(message)
        try: choice = int(choice)
        except ValueError: choice = -1
        if choice < 0 or choice >= len(choices):
            print 'Invalid input.'
            print
    return choices[choice]

def main():
    if len(sys.argv) < 2:
        print >> sys.stderr, 'Usage: python upload2ourbricks.py file1 [file2 [file3 ..]]'
        sys.exit(1)
    
    opts, args = getopt.getopt(sys.argv[1:], ':')
    upload_files = args
    for f in upload_files:
        if not os.path.isfile(f):
            print >> sys.stderr, 'File not found: %s' % (f,)
            sys.exit(1)
    
    consumer = oauth2.Consumer(CONSUMER_KEY, CONSUMER_SECRET)
    client = oauth2.Client(consumer)
    
    # Step 1: Get a request token. This is a temporary token that is used for 
    # having the user authorize an access token and to sign the request to obtain 
    # said access token.
    
    resp, content = client.request(REQUEST_TOKEN_URL, "GET")
    if resp['status'] != '200':
        exitprint(resp, content)
    
    request_token = dict(urlparse.parse_qsl(content))
    
    print "Request Token:"
    print "    - oauth_token        = %s" % request_token['oauth_token']
    print "    - oauth_token_secret = %s" % request_token['oauth_token_secret']
    print 

    # Step 2: Redirect to the provider. Since this is a CLI script we do not 
    # redirect. In a web application you would redirect the user to the URL
    # below.
    
    print "Go to the following link in your browser:"
    print "%s?oauth_token=%s" % (AUTHORIZATION_URL, request_token['oauth_token'])
    print 
    
    # After the user has granted access to you, the consumer, the provider will
    # redirect you to whatever URL you have told them to redirect to. You can 
    # usually define this in the oauth_callback argument as well.
    accepted = raw_input('Have you authorized me? (y/n) ')
    if accepted != 'y':
        print "Well, then nothing to do here. Exiting"
        sys.exit(0)
    oauth_verifier = raw_input('What is the PIN? ')
    
    # Step 3: Once the consumer has redirected the user back to the oauth_callback
    # URL you can request the access token the user has approved. You use the 
    # request token to sign this request. After this is done you throw away the
    # request token and use the access token returned. You should store this 
    # access token somewhere safe, like a database, for future use.
    token = oauth2.Token(request_token['oauth_token'],
        request_token['oauth_token_secret'])
    token.set_verifier(oauth_verifier)
    client = oauth2.Client(consumer, token)
    
    resp, content = client.request(ACCESS_TOKEN_URL, "POST")
    access_token = dict(urlparse.parse_qsl(content))
    if resp['status'] != '200':
        exitprint(resp, content)
    
    print "Access Token:"
    print "    - oauth_token        = %s" % access_token['oauth_token']
    print "    - oauth_token_secret = %s" % access_token['oauth_token_secret']
    print

    # Step 4: We have an access token, so we can issue
    # an upload request on behalf of the user
    
    token = oauth2.Token(access_token['oauth_token'],
                         access_token['oauth_token_secret'])
    
    upload_params = dict(title=raw_input('Title: '),
                         description=raw_input('Description: '),
                         tags=raw_input('Tags: '),
                         author=raw_input('Author: '))
    license = get_choice('Choose A License: ', LICENSE_CHOICES)
    upload_params['license'] = license
    if license == 'For Sale':
        price = -1.0
        while price < 0:
            price = raw_input('Price: ')
            try: price = float(price)
            except ValueError: price = -1
            if price < 0:
                print 'Invalid input.'
                print
    else:
        price = ''
    upload_params['price'] = str(price)
    
    req = oauth2.Request.from_consumer_and_token(consumer,
                                                 token=token,
                                                 http_method="POST",
                                                 http_url=UPLOAD_URL,
                                                 parameters=upload_params)

    req.sign_request(oauth2.SignatureMethod_HMAC_SHA1(), consumer, token)
    compiled_postdata = req.to_postdata()
    all_upload_params = urlparse.parse_qs(compiled_postdata, keep_blank_values=True)
    
    #parse_qs returns values as arrays, so convert back to strings
    for key, val in all_upload_params.iteritems():
        all_upload_params[key] = val[0]
    
    for i, fpath in enumerate(upload_files):
        all_upload_params['file' + str(i)] = open(fpath, 'rb')
    datagen, headers = multipart_encode(all_upload_params)
    request = urllib2.Request(UPLOAD_URL, datagen, headers)
    
    try:
        respdata = urllib2.urlopen(request).read()
    except urllib2.HTTPError, ex:
        print >> sys.stderr, 'Received error code: ', ex.code
        print >> sys.stderr
        print >> sys.stderr, ex
        sys.exit(1)
        
    result = json.loads(respdata)
    if result.get('success') != True or 'uploadid' not in result:
        print >> sys.stderr, 'Upload failed. Error = ', result.get('error')
        print >> sys.stderr
        sys.exit(1)
    
    uploadid = result['uploadid']
    print 'Succeeded in submitting upload. Upload id = %s Checking status...' % (uploadid,)
    print
    
    client = oauth2.Client(consumer, token)
    
    complete = False
    while not complete:
        resp, content = client.request('%s?uploadid=%s' % (UPLOAD_STATUS_URL, uploadid), "GET")
        if resp['status'] != '200':
            exitprint(resp, content)
        result = json.loads(content)
        if 'complete' not in result:
            exitprint(resp, content)
        complete = result['complete']
        if not(complete == False or complete == True):
            complete = False
        if complete == False:
            print 'Not complete. Status = %s' % (result.get('status_message').strip())
        time.sleep(2)
        
    print
    print 'Finished. Status = %s' % (result.get('status_message'),)
    print
    print 'You can find your upload at: %s%s' % (VIEWER_URL, uploadid)
    
if __name__ == '__main__':
    main()
