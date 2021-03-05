import typer
from opset import setup_config

from tbot import bot

setup_config("tbot", "tbot.config")
cli = typer.Typer()


@cli.command()
def main():
    typer.secho("Starting Twitter bot", fg="blue")
    bot.bot()


if __name__ == '__main__':
    cli()
