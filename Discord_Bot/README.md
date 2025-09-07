# Discord Bot

This bot is designed to connect [Crafty Servers](https://craftycontrol.com) to a discord Bot

## Features  

- Start Crafty Serves on demand
- Stop Crafty Servers on demand
- Server statues on demand
- Discord statues Channel
- Granular control of which servers Bot has access to



## Configuration

Inside [docker-compose.yml](docker-compose.yml) 

```yml
environment:
  DISCORD_TOKEN: "Token Goes Here"
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


