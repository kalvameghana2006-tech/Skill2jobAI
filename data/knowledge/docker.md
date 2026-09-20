# Docker

> Packaging apps and dependencies into portable containers using images, Dockerfiles and Compose.
> Category: DevOps & Cloud. Typical effort: about 6 study days.

## Containers vs virtual machines

- **Container** — isolated process sharing the host kernel.
- **Virtual machine** — full guest OS running on a hypervisor.
- **Image** — read-only template used to create containers.

Practice: Install Docker and run hello-world, nginx and an interactive ubuntu container.

## Images and containers in practice

- **docker run** — creates and starts a container from an image.
- **docker ps** — lists running containers.
- **Docker Hub** — public registry for sharing images.

Practice: Pull, tag and remove images; map a container port to your laptop.

## Writing a Dockerfile

- **FROM** — sets the base image.
- **COPY** — adds files into the image.
- **CMD** — default command run when the container starts.
- **Layer caching** — unchanged steps are reused to speed up builds.

Practice: Write a Dockerfile for a small web app and build it.

## Volumes and networks

- **Volume** — persistent storage that outlives a container.
- **Bridge network** — default network letting containers talk by name.
- **Port mapping** — exposes a container port on the host.

Practice: Run a database container with a named volume and connect an app to it.

## Docker Compose

- **docker-compose.yml** — declares multi-container apps in one file.
- **depends_on** — controls service start order.
- **Environment variables** — configure containers without rebuilding images.

Practice: Compose an app + database stack and bring it up with one command.

## Best practices

- **Multi-stage build** — uses one stage to build and a slim stage to run.
- **.dockerignore** — excludes files from the build context.
- **Non-root user** — limits damage if a container is compromised.

Practice: Shrink your image with a multi-stage build.

## Mini project

Containerize a Spring Boot (or Flask) app plus a MySQL database with Docker Compose and document how to run it.
