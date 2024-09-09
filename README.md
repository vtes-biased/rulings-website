# VTES rulings website

## Develop

You'll need [Python3](https://www.python.org) and [NodeJS](https://nodejs.org) to build the project.

### Setting up the development environment

Create a Python virtual env, an `.env` file, and install:

```shell
$ python3 -m venv .venv
$ touch .env
$ make update
```

You want a couple of env variables for tha app to run correctly:

```shell
export QUART_APP="vtesrulings:app"
export DISCORD_WEBHOOK=<your Discord community server webhook URL>
```

You can now launch the server locally:

```shell
§ make serve
```
