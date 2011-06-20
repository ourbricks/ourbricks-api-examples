<?php

require_once 'oauth-php/library/OAuthStore.php';
require_once 'oauth-php/library/OAuthRequester.php';
require_once 'oauth-php/library/body/OAuthBodyMultipartFormdata.php';

/*
 * Set these to your application's key and secret
 */ 
define("OURBRICKS_CONSUMER_KEY", "YOUR_CONSUMER_KEY_HERE");
define("OURBRICKS_CONSUMER_SECRET", "YOUR_SECRET_KEY_HERE");


/*
 * The path to the file on the server that will be uploaded
 */ 
define("FILE_UPLOAD", "./FILE_TO_UPLOAD.dae");

/*
 * This is the callback URL to go back to your site after the user authorizes
 * your application. This will set it to the current script, but you may wish
 * to customize it.
*/
$PORT = "";
if ($_SERVER["SERVER_PORT"] != "80") {
	$PORT = ":" . $_SERVER["SERVER_PORT"];
}
$CALLBACK_URL = 'http://' . $_SERVER["SERVER_NAME"] . $PORT . $_SERVER["REQUEST_URI"];

/*
 *  These are the ourbricks oauth endpoints
 *  You shouldn't have to change these
 */
define("OURBRICKS_OAUTH_HOST", "http://ourbricks.com");
define("OURBRICKS_REQUEST_TOKEN_URL", OURBRICKS_OAUTH_HOST . "/oauth-request-token");
define("OURBRICKS_AUTHORIZE_URL", OURBRICKS_OAUTH_HOST . "/oauth-authorize");
define("OURBRICKS_ACCESS_TOKEN_URL", OURBRICKS_OAUTH_HOST . "/oauth-access-token");
define("OURBRICKS_UPLOAD_URL", OURBRICKS_OAUTH_HOST . "/api/upload");

define('OAUTH_TMP_DIR', function_exists('sys_get_temp_dir') ? sys_get_temp_dir() : realpath($_ENV["TMP"]));

//  Init the OAuthStore
$options = array(
	'consumer_key' => OURBRICKS_CONSUMER_KEY, 
	'consumer_secret' => OURBRICKS_CONSUMER_SECRET,
	'server_uri' => OURBRICKS_OAUTH_HOST,
	'request_token_uri' => OURBRICKS_REQUEST_TOKEN_URL,
	'authorize_uri' => OURBRICKS_AUTHORIZE_URL,
	'access_token_uri' => OURBRICKS_ACCESS_TOKEN_URL
);
// Note: do not use "Session" storage in production. Prefer a database
// storage, such as MySQL.
OAuthStore::instance("Session", $options);

try
{
	//  STEP 1:  If we do not have an OAuth token yet, go get one
	if (empty($_GET["oauth_token"]))
	{
		$getAuthTokenParams = array('oauth_callback' => $CALLBACK_URL);

		// get a request token
		$tokenResultParams = OAuthRequester::requestRequestToken(OURBRICKS_CONSUMER_KEY, 0, $getAuthTokenParams);

		// redirect to the authorization page, they will redirect back
		header("Location: " . OURBRICKS_AUTHORIZE_URL . "?oauth_token=" . $tokenResultParams['token']);
	}
	else {
		//  STEP 2:  Get an access token
		$oauthToken = $_GET["oauth_token"];
		
		$tokenResultParams = $_GET;
		
		try {
		    OAuthRequester::requestAccessToken(OURBRICKS_CONSUMER_KEY, $oauthToken, 0, 'POST', $_GET);
		}
		catch (OAuthException2 $e)
		{
			var_dump($e);
		    // Something wrong with the oauth_token.
		    // Could be:
		    // 1. Was already ok
		    // 2. We were not authorized
		    return;
		}
		
		// STEP 3: We now have an access token, so we can do the upload request
		$files = array(
					array('file' => FILE_UPLOAD)
					);
		
		$form_vars = array();
		$form_vars['title'] = 'my test title';
		$tokenResultParams = array_merge($tokenResultParams, $form_vars);
		
		list($headers, $body) = OAuthBodyMultipartFormdata::encodeBody($form_vars, $files);
		
		$curl_opts = array();
		foreach ($headers as $h => $v) {
			$curl_opts[] = $h . ": " . $v;
		}
		$curl_opts = array(CURLOPT_HTTPHEADER => $curl_opts);
		
	   	$request = new OAuthRequester(OURBRICKS_UPLOAD_URL, 'POST', $tokenResultParams, $body);
        $result = $request->doRequest(0, $curl_opts);
        if ($result['code'] == 200) {
        	var_dump($result['body']);
        }
        else {
        	echo 'Error';
        }
	}
}
catch(OAuthException2 $e) {
	echo "OAuthException:  " . $e->getMessage();
	var_dump($e);
}
?>