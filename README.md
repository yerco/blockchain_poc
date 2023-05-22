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
(env)$ python manage.py run -h 0.0.0.0 --no-debug
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

If you don't want to use `curl` or a similar alternative there's a basic frontend:
```bash
$ cd frontend
$ npm install
$ npm start
```
Then go to http://<your-host>:3000/

## ZMQ
Set the value `COMM = 'zmq'`, all the nodes are stored in the DB.
The problem of a node being down has not being solved.
All the nodes establish connections among them.

## Kafka (with Zookeeper)

At config set the value `COMM = 'kafka'`. You need to create the topics `transaction`, `chain` and `node` (this last
one is not relevant for kafka at this point), ex:
```bash
$ kafka-topics.sh --create --zookeeper localhost:2181 --replication-factor 2 --partitions 3 --topic transaction
```

You can produce transactions using the API (see `curl` example above) or using a producer, ex:
```bash
$ kafka-console-producer.sh --broker-list localhost:9092 --topic transaction
```

## TODOs
- This is a newly born WIP, so many things to do.
- Solve transaction conflict resolution problems.
- More test needed most of the existing ones are **flaky** do not trust them they are not by any chance a good example.
- Related with the previous issue, Kafka tests need the services running, will find a way to make it solid.

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
