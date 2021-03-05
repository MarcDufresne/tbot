from collections import defaultdict
from datetime import datetime
from time import sleep

import httpx
import telebot
import typer
from opset import config

from tbot import utils


def bot():
    telegram = telebot.TeleBot(config.telegram.token, parse_mode="MarkdownV2")
    typer.secho("Initialized Telegram client")

    last_check_per_account = defaultdict(lambda: datetime.utcnow())

    while True:
        for twitter_acc_id in config.twitter.accounts:
            typer.secho(f"Checking for new Tweets by account ID {twitter_acc_id}")
            resp = httpx.get(
                f"https://api.twitter.com/2/users/{twitter_acc_id}/tweets",
                params={"tweet.fields": "text,created_at,in_reply_to_user_id", "expansions": "author_id"},
                headers={"Authorization": f"Bearer {config.twitter.token}"}
            )

            try:
                resp.raise_for_status()
                typer.secho(f"Got Tweets for account {twitter_acc_id}")
            except httpx.HTTPError as he:
                typer.secho(f"Error while contacting Twitter's API: {str(he)}", fg="red")
                exit(1)

            check_time = last_check_per_account[twitter_acc_id]
            last_check_per_account[twitter_acc_id] = datetime.utcnow()

            resp_data = resp.json()
            reverse_order_tweets = list(reversed(resp_data["data"]))
            username = resp_data["includes"]["users"][0]["username"]

            if config.debug.generate_recent_tweet:
                typer.secho("DEBUG: Generating a recent Tweet", fg="magenta")
                now_string = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
                reverse_order_tweets.insert(0, {
                    "text": "THIS IS A FAKE TWEET! ⚠",
                    "created_at": f"{now_string}.000Z"
                })

            for tweet in reverse_order_tweets:
                tweet_parsed_date = datetime.strptime(tweet["created_at"][:-5], "%Y-%m-%dT%H:%M:%S")
                tweet_text = tweet["text"]
                log_tweet_text = tweet_text.replace('\n', ' ')

                if tweet.get("in_reply_to_user_id"):
                    typer.secho(f"Ignoring reply Tweet: {log_tweet_text}", fg="yellow")
                    continue

                typer.secho(f"Checking Tweet: {log_tweet_text}")

                if tweet_parsed_date >= check_time:
                    typer.secho(f"New Tweet found! {log_tweet_text}")

                    telegram_tweet_username = utils.escape_telegram_text(username)
                    telegram_tweet_text = utils.escape_telegram_text(tweet_text)
                    telegram_text = f"*New Tweet from {telegram_tweet_username}*\n\n{telegram_tweet_text}"

                    try:
                        telegram.send_message(config.telegram.chat_id, telegram_text)
                    except Exception as e:
                        typer.secho(f"Error sending Telegram message: {str(e)}", fg="red")

                    typer.secho("Telegram message sent!", fg="green")

        sleep(config.sleep)
