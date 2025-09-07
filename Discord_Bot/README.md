# Discord Bot

This bot is designed to connect [Crafty Servers](https://craftycontrol.com) to a discord Bot


## Features  

- Start Crafty Serves on demand
- Stop Crafty Servers on demand
- Server statues on demand
- Discord statues Channel
- Granular control of which servers Bot has access to


## Prerequisites

- Docker installation
- [Discord_Bot ](/Discord_Bot/) Folder pulled from this repo
- Discord Bot Token 

### - Docker Installation on a Linux system

Make sure system is up to date

```
apt update
apt upgrade
```

Install docker
```
apt install docker.io 
```

## Bot Configuration

Inside [docker-compose.yml](docker-compose.yml) 

```yml
environment:
  DISCORD_TOKEN: "Token Goes Here"
```

Inside [config.yaml](/Discord_Bot/config/config.yaml) 

```yml
base_url: "https://localhost:8443" # Adjust accordingly 
username: "admin" # Crafty User Name
password: "password" # Crafty Paasword
verify_ssl: false # untested...
update_interval: 300 # can leave as is due to discord 2/10 rule
category_name: "Crafty Servers" # Discord catagory name of you`re choice
allowed_user_ids:
  - 123456789012345678 # edit/add as many as you want
allowed_role_names:
  - "CraftyAdmin" # edit/add as many as you want
servers:  
example: "UUID" #Name of you`re Choice : Crafty Server UUID
```

## Turning it into Docker Container

Once you have this folder/repo

Prepping to turn into docker image and container

```
cd /its/location
```

Turns it into Docker image and also into a running container (will need docker to be installed on the system)
```
docker-compose up -d --build
```


