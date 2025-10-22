# Backup environment

Make backup for .env file.
Check if all values in .env.example are present in .env and vice versa
Use commands cat .env and cat .env.example to see these protected files.
Add all non-secret variable names (keys only, without values) that are missing from .env into .env.example.
Never include secret values in .env.example.
