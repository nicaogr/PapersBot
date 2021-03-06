#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PapersBot
#
# purpose:  read journal RSS feeds and tweet selected entries
# license:  MIT License
# author:   François-Xavier Coudert
# e-mail:   fxcoudert@gmail.com
# updated:  2018-06-16
#

import bs4, feedparser, tweepy
import imghdr, os, re, sys, tempfile, time, urllib, yaml


# Twitter parameters
# These values should be queried "no more than once a day" by 
# tweepy's api.configuration(), but for now they are fixed here.
TWEET_MAX_LENGTH = 280
TWEET_URL_LENGTH = 24
TWEET_IMG_LENGTH = 25
TWEET_NET_LENGTH = TWEET_MAX_LENGTH - TWEET_URL_LENGTH - TWEET_IMG_LENGTH


# This is the regular expression that selects the papers of interest
regex = re.compile(r"""
  (   \b(MOF|MOFs|COF|COFs)\b
    | metal.organic.framework
    | covalent.organic.framework
    | metal–organic.framework
    | covalent–organic.framework
    | porous.coordination.polymer
  )
  """, re.IGNORECASE | re.VERBOSE)


# Global variable
posted = []


# We select entries based on title or summary (abstract, for some feeds)
def entryMatches(entry):
  if regex.search(entry.title):
    return True
  if "summary" in entry:
    return regex.search(entry.summary)
  else:
    return False


# Find the URL for an image associated with the entry
def findImage(entry):
  soup = bs4.BeautifulSoup(entry.description, "html.parser")
  img = soup.find("img")
  if img:
    img = img["src"]
    # If address is relative, append root URL
    if img[0] == "/":
      p = urllib.parse.urlparse(entry.id)
      img = f"{p.scheme}://{p.netloc}" + img

  return img


# Convert string from HTML to plain text
def htmlToText(s):
  return bs4.BeautifulSoup(s, "html.parser").get_text()


def downloadImage(url):
  if not url: return None

  try:
    img, _ = urllib.request.urlretrieve(url)
  except:
    return None
  ext = imghdr.what(img)
  res = img + "." + ext
  os.rename (img, res)

  # Images smaller than 4 KB have a problem, and Twitter will complain
  if os.path.getsize(res) < 4096:
    os.remove(res)
    return None

  return res


# Connect to Twitter and authenticate
#   Credentials are stored in "credentials.yml" which contains four lines:
#   CONSUMER_KEY: "x1F3s..."
#   CONSUMER_SECRET: "3VNg..."
#   ACCESS_KEY: "7109..."
#   ACCESS_SECRET: "AdnA..."
#
def initTwitter():
  with open("credentials.yml", "r") as f:
    cred = yaml.load(f)
  auth = tweepy.OAuthHandler(cred["CONSUMER_KEY"], cred["CONSUMER_SECRET"])
  auth.set_access_token(cred["ACCESS_KEY"], cred["ACCESS_SECRET"])
  api = tweepy.API(auth)
  return api


# Read our list of feeds from file
def readFeedsList():
  with open("feeds.txt", "r") as f:
    feeds = [s.partition("#")[0].strip() for s in f]
    return [s for s in feeds if s]


# Remove unwanted text some journals insert into the feeds
def cleanText(s):
  # Annoying ASAP tags
  if "[ASAP]" in s:
    s = s.replace("[ASAP]", "")

  # Some feeds have LF characeters
  s = s.replace("\x0A", "")

  # Remove multiple spaces, leading and trailing space
  return re.sub("\s\s+" , " ", s).strip()


# Read list of feed items already posted
def readPosted():
  try:
    with open("posted.dat", "r") as f:
      return f.read().splitlines()
  except:
    return []


# Add to tweets posted
def addToPosted(url):
  with open("posted.dat", "a+") as f:
    print(url, file=f)
  posted.append(url)


# Send a tweet for a given feed entry
def sendTweet(entry, api):
  title = cleanText(htmlToText(entry.title))
  url = entry.id
  tweet_body = title[:TWEET_NET_LENGTH] + " " + url

  image = findImage(entry)
  image_file = downloadImage (image)

  if image_file:
    print(f"TWEET: {tweet_body}\nIMAGE: {image}\n")
    if api:
      api.update_with_media (image_file, tweet_body)
    os.remove (image_file)
  else:
    print(f"TWEET: {tweet_body}\n")
    if api:
      api.update_status (tweet_body)

  addToPosted(entry.id)
  if api:
    time.sleep(5)


def main():
  # Make sure all options are correctly typed
  for arg in sys.argv[1:]:
    if not arg in ["--do-not-tweet"]:
      print(f"Unknown option: {arg}")
      sys.exit(1)

  feeds = readFeedsList()
  posted = readPosted()

  # Connect to Twitter, unless requested not to
  if "--do-not-tweet" in sys.argv:
    api = None
  else:
    api = initTwitter()

  print(f"This is PapersBot running at {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
  if api:
    last = api.user_timeline(count = 1)[0].created_at
    print(f"Last tweet was posted at {last} (UTC)")
  print(f"Feed list has {len(feeds)} feeds\n")

  for feed in feeds:
    parsed_feed = feedparser.parse(feed)
    for entry in parsed_feed.entries:
      if entryMatches(entry):
        # If no ID provided, use the link as ID
        if not "id" in entry: entry.id = entry.link
        if not entry.id in posted:
          sendTweet(entry, api)


if __name__ == '__main__':
  main()
