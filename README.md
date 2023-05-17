# Blockchain PoC

Concepts taken from [this](https://youtu.be/nhA9I_RYxgQ)

## Tools used
- Python 3.11
- MySQL > 5.7 (also tested using MariaDB > 10.5)

## Install
```
$ pip install -r requirements.txt
```

Problems with `fastecdsa` see https://github.com/stacks-network/stacks-blockchain/issues/318

Problems when installing `pip install flask-mysqldb`:
```bash
$ sudo apt-get install mysql-server
$ sudo apt-get install mysql-client
$ sudo apt-get install libmysqlclient-dev
```
Then pip install again

## Run

```sql
CREATE DATABASE flaskchain_dev;
CREATE DATABASE flaskchain_test;   
```

```bash
(env)$ python manage.py run -h 0.0.0.0
```
Note: at `utilities.py`::`generate_key_pair` can be used to generate a key pair.

Send transactions
```bash
curl --header "Content-Type: application/json" \
     --request POST  \
     --data '{"full_names":"Some names","practice_number":"1234567890","notes":"Some notes"}' \
     http://localhost:8888/transactions
```
* There are more endpoints (check).

## TODOs
- This is a newly born WIP, so many things to do.
- Solve transaction conflict resolution problems.
- More test needed most of the existing ones are **flaky** ![](https://www.jetbrains.com/teamcity/ci-cd-guide/concepts/flaky-tests/)
- Related with the previous issue, Kafka tests need the services running, find a way to make it solid.

### Bonus track: Primitive CI/CD explained in the video
```bash
$ git init --bare
```
- Create a file `hooks/post-receive`
- refs:
    - https://www.digitalocean.com/community/tutorials/how-to-use-git-hooks-to-automate-development-and-deployment-tasks
    - https://gist.github.com/nonbeing/f3441c96d8577a734fa240039b7113db
```bash
#!/bin/bash
while read oldrev newrev ref
do
if [[ $ref =~ .*/main$ ]];
then
echo "Main ref received.  Deploying master branch to production..."
git --work-tree=/home/ubuntu/skolo02/python_blockchain --git-dir=/home/ubuntu/skolo02/repo checkout -f
else
echo "Ref $ref successfully received.  Doing nothing: only the main branch may be deployed on this server."
fi
done
```
