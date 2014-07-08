socialmailbox
============

Minimal server websocket router for matchmaking. Now with persistence.

on connect, client needs to send either
```{'cmd': 'login', 'user':'<username>','password':'<password>'}```

or register with
```{'cmd': 'register', 'user':'<username>', 'password':'<password>'}```

Installing
------------

    pip install --user -r requirements.txt


Running
-------------

    python router.py