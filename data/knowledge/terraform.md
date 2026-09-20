# Terraform

> Declaring cloud infrastructure as code with providers, state and modules.
> Category: DevOps & Cloud. Typical effort: about 8 study days.

## Terraform basics

- **Provider** — plugin that talks to a cloud API.
- **Resource** — infrastructure object declared in code.
- **terraform plan** — previews the changes before applying.

Practice: Create one resource and destroy it.

## State and variables

- **State file** — records what Terraform manages.
- **Variable** — input that makes configuration reusable.
- **Output** — value exposed after apply.

Practice: Parameterize a configuration with variables.

## Modules and workflow

- **Module** — reusable group of resources.
- **Remote backend** — stores state safely for teams.
- **terraform apply** — makes the real infrastructure match the code.

Practice: Turn your resources into a module.

## Mini project

Provision a network, a virtual machine and a storage bucket with Terraform modules and remote state.
