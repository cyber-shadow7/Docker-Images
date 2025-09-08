# Discord Bot

This bot is designed to connect [Crafty Servers](https://craftycontrol.com) to a discord Bot


## Features  

- Start Crafty Serves on demand
- Stop Crafty Servers on demand
- Server statues on demand
- Discord status Channel
- Granular control of which servers Bot has access to
- Granular control of which users and roles can use the bot

## Prerequisites

- Docker & Docker Compose Installed
- [Discord Bot Token](https://discord.com/developers/applications)
- A clone of this repository 
```
git clone https://github.com/cyber-shadow7/Docker-Images.git
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
cd Docker-Images/Discord_Bot
```

Turns it into Docker image and also into a running container (will need docker to be installed on the system)
```
docker-compose up -d --build
```
Confirming Container is running
```
docker-compose ps
```
To check logs (have to be cd into project folder)
```
docker-compose logs -f
```
