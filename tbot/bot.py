from collections import defaultdict
from datetime import datetime, timezone
from time import sleep

import httpx
import telebot
import typer
from opset import config

from tbot import utils


def bot():
    telegram = telebot.TeleBot(config.telegram.token, parse_mode="MarkdownV2")
    typer.secho("Initialized Telegram client")

    startup_time = datetime.now(timezone.utc)
    last_tweet_id_per_account = defaultdict(str)

    while True:
        for twitter_account_config in config.twitter.accounts:
            twitter_account_name = twitter_account_config["name"]
            include_replies = twitter_account_config.get("replies", False)

            typer.secho(f"Checking for new Tweets by account ID {twitter_account_name}")

            params = {"screen_name": twitter_account_name}
            if last_tweet_id_per_account[twitter_account_name]:
                params["since_id"] = last_tweet_id_per_account[twitter_account_name]
            else:
                params["count"] = 1

            resp = httpx.get(
                f"https://api.twitter.com/1.1/statuses/user_timeline.json",
                params=params,
                headers={"Authorization": f"Bearer {config.twitter.token}"},
            )

            try:
                if resp.status_code == 429:
                    typer.secho("Rate-limited by Twitter, waiting a bit...", fg="yellow")
                    sleep(config.sleep)
                    continue

                resp.raise_for_status()
                typer.secho(f"Got Tweets for account {twitter_account_name}")
            except httpx.HTTPError as he:
                typer.secho(f"Error while contacting Twitter's API: {str(he)}", fg="red")
                exit(1)

            resp_data = resp.json()

            if not resp_data and not config.debug.fake_tweet:
                typer.secho(f"No new Tweets found for account {twitter_account_name}")
                continue
            elif config.debug.fake_tweet:
                resp_data = [
                    {
                        "id": "1368728646609932298",
                        "text": "THIS IS A FAKE TWEET! ⚠",
                        "created_at": datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S %z %Y"),
                    }
                ]

            last_tweet_id_per_account[twitter_account_name] = resp_data[0]["id"]

            reverse_order_tweets = list(reversed(resp_data))

            for tweet in reverse_order_tweets:
                tweet_parsed_date = datetime.strptime(tweet["created_at"], "%a %b %d %H:%M:%S %z %Y")
                if tweet_parsed_date < startup_time:
                    typer.secho("Ignoring Tweet older than start time", fg="yellow")
                    continue

                tweet_url = f"https://twitter.com/{twitter_account_name}/status/{tweet['id']}"
                tweet_is_reply = tweet.get("in_reply_to_user_id")
                tweet_text = tweet["text"]
                log_tweet_text = tweet_text.replace("\n", " ")

                if tweet_is_reply and not include_replies:
                    typer.secho(f"Ignoring reply Tweet: {log_tweet_text}", fg="yellow")
                    continue

                typer.secho(f"New Tweet found! {log_tweet_text}")

                telegram_tweet_username = utils.escape_telegram_text(twitter_account_name)
                telegram_tweet_text = utils.escape_telegram_text(tweet_text)
                telegram_title = f"New Tweet from {telegram_tweet_username}"
                telegram_text = f"*[{telegram_title}]({tweet_url})*\n\n{telegram_tweet_text}"

                try:
                    telegram.send_message(config.telegram.chat_id, telegram_text)
                except Exception as e:
                    typer.secho(f"Error sending Telegram message: {str(e)}", fg="red")

                typer.secho("Telegram message sent!", fg="green")

        sleep(config.sleep)
