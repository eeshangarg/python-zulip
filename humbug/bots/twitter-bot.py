#!/usr/bin/env python
import os
import sys
import optparse
import ConfigParser
from os import path

CONFIGFILE = os.path.expanduser("~/.humbug_twitterrc")

sys.path.append(path.join(path.dirname(__file__), '../..'))
import humbug

def write_config(config, since_id, user):
    config.set('twitter', 'since_id', since_id)
    config.set('twitter', 'user_id', user)
    with open(CONFIGFILE, 'wb') as configfile:
        config.write(configfile)

parser = optparse.OptionParser(r"""

%prog --user foo@humbughq.com --twitter_id twitter_handle

    Slurp tweets on your timeline into a specific humbug stream.

    Run this on your personal machine.  Your API key and twitter id are revealed to local
    users through the command line or config file.

    This bot uses OAuth to authenticate with twitter. Please create a ~/.humbug_twitterrc with
    the following contents:

    [twitter]
    consumer_key =
    consumer_secret =
    access_token_key =
    access_token_secret =

    In order to obtain a consumer key & secret, you must register a new application under your twitter account:

    1. Go to http://dev.twitter.com
    2. Log in
    3. In the menu under your username, click My Applications
    4. Create a new application

    Make sure to go the application you created and click "create my access token" as well. Fill in the values displayed.

    Depends on: twitter-python
""")

parser.add_option('--user',
    help='Humbug user email address',
    metavar='EMAIL')
parser.add_option('--api-key',
    help='API key for that user [default: read ~/.humbugrc]')
parser.add_option('--twitter-id',
    help='Twitter username to poll for new tweets from"',
    metavar='URL')
parser.add_option('--site',
    default="https://humbughq.com",
    help='Humbug site [default: https://humbughq.com]',
    metavar='URL')
parser.add_option('--stream',
    help='Default humbug stream to write tweets to')
parser.add_option('--limit-tweets',
    default=15,
    type='int',
    help='Maximum number of tweets to push at once')

(options, args) = parser.parse_args()

if not options.twitter_id:
    parser.error('You must specify --twitter-id')

try:
    config = ConfigParser.ConfigParser()
    config.read(CONFIGFILE)

    consumer_key = config.get('twitter', 'consumer_key')
    consumer_secret = config.get('twitter', 'consumer_secret')
    access_token_key = config.get('twitter', 'access_token_key')
    access_token_secret = config.get('twitter', 'access_token_secret')
except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
   parser.error("Please provide a ~/.humbug_twitterrc")

if not consumer_key or not consumer_secret or not access_token_key or not access_token_secret:
   parser.error("Please provide a ~/.humbug_twitterrc")

try:
    import twitter
except ImportError:
    parser.error("Install twitter-python")

api = twitter.Api(consumer_key=consumer_key,
                  consumer_secret=consumer_secret,
                  access_token_key=access_token_key,
                  access_token_secret=access_token_secret)


user = api.VerifyCredentials()

if not user.GetId():
    print "Unable to log in to twitter with supplied credentials. Please double-check and try again"
    sys.exit()

try:
    since_id = config.getint('twitter', 'since_id')
except ConfigParser.NoOptionError:
    since_id = -1

try:
    user_id = config.get('twitter', 'user_id')
except ConfigParser.NoOptionError:
    user_id = options.twitter_id

client = humbug.Client(
    email=options.user,
    api_key=options.api_key,
    site=options.site,
    verbose=True)

if since_id < 0 or options.twitter_id != user_id:
    # No since id yet, fetch the latest and then start monitoring from next time
    # Or, a different user id is being asked for, so start from scratch
    # Either way, fetch last 5 tweets to start off
    statuses = api.GetFriendsTimeline(user=options.twitter_id, count=5)
else:
    # We have a saved last id, so insert all newer tweets into the humbug stream
    statuses = api.GetFriendsTimeline(user=options.twitter_id, since_id=since_id)

for status in statuses[::-1][:options.limit_tweets]:
    composed = "%s (%s)" % (status.GetUser().GetName(), status.GetUser().GetScreenName())
    message = {
      "type": "stream",
      "to": [options.stream],
      "subject": composed,
      "content": status.GetText(),
    }

    ret = client.send_message(message)

    if ret['result'] == 'error':
        # If sending failed (e.g. no such stream), abort and retry next time
        print "Error sending message to humbug: %s" % ret['msg']
        break
    else:
        since_id = status.GetId()

write_config(config, since_id, user_id)
