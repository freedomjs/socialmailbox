#!/usr/bin/env python
"""
Websocket rendezvous with persistent accounts.
Listens on http://localhost:8083/route
  Depends on python-tornado
"""
import os, sys, inspect
here = os.path.abspath(os.path.split(inspect.getfile(inspect.currentframe()))[0])
if os.path.join(here, "tornado") not in sys.path:
  sys.path.insert(0, os.path.join(here, "tornado"))

import tornado.escape
import tornado.ioloop
import tornado.websocket
import tornado.web
import uuid
import sqlite3  
import hashlib

class Application(tornado.web.Application):
  def __init__(self):
    handlers = [(r"/route/([a-zA-Z0-9_]*)", MainHandler)]
    settings = dict( autoescape=None )
    tornado.web.Application.__init__(self, handlers, **settings)

class MainHandler(tornado.websocket.WebSocketHandler):
  test = sqlite3.connect('user.db')

  test.executescript("create table if not exists users (id varchar primary key, salt varchar, hash varchar);")

  waiters = dict()  #userid => WebSocketHandler
  msg_dict = dict() #pendingMsgs 

  def allow_draft76(self):
    return True

  
  def open(self, app_id):
    if (app_id == None or app_id == ''):
      app_id = self.request.headers.get("Origin")
    
  def on_finish(self):
    self.on_close()
  
  # Close connection
  def on_close(self):
    if hasattr(self, 'id'):
      # Cleanup global state
      del MainHandler.waiters[self.id]

  # On incoming message
  def on_message(self, msg):
    val = tornado.escape.json_decode(msg)
    if val['cmd'] == 'register': 
      if len(val['user']) > 3 and len(val['user']) < 20 and len(val['password']) > 3: 
          with MainHandler.test: 
            salt = os.urandom(16)
            cur = MainHandler.test.cursor()
            cur.execute("INSERT INTO users (id,salt,hash) VALUES(?,?,?);",
                (val['user'], salt, hashlib.sha256(val['password'] + salt)))
    elif val['cmd'] == 'login':
      with MainHandler.test: 
            cur = MainHandler.test.cursor()
            results = cur.execute("SELECT salt,hash FROM users WHERE id=?", (val['user']))
            for r in results.fetchall(): 
              if hashlib.sha256(r[0] + val['password']) == str(r[1]):
                self.write_message({ #goes to social.mb.js, onMessage
                  'user': val['user'], 
                  'cmd': "login"
                }) 
                self.id = val['user']
                MainHandler.waiters[self.id] = self
                print "MAIN HANDLER WAITER>>>>>>>>>>>>" + self.id

                #look at pending msgs 
                if self.id in MainHandler.msg_dict: 
                  print "MSGS WAITING______________________" + str(MainHandler.msg_dict[self.id][0]['msg'])
                else: 
                  print "NO MSGS WAITING______________________"

    elif val['cmd'] == 'send':
      to = val['to']
      if to in MainHandler.waiters: 
        MainHandler.waiters[to].write_message({ #goes to social.mb.js, onMessage
          'msg' : val['msg'],
          'cmd' : 'send'
        })
        print val['msg'] + "**********"

      else:
        print 'q msg========================================' + self.id
        msg = {
          'from' : self.id,
          'msg' : val['msg'], 
          'timestamp' : '2'  
        }
        msg_q = []
        if to in MainHandler.msg_dict: 
          msg_q = MainHandler.msg_dict[to]

        msg_q.append(msg)
        MainHandler.msg_dict[to] = msg_q

    elif val['cmd'] == 'get_users':
      with MainHandler.test:
        cur = MainHandler.test.cursor() 
        results = cur.execute("SELECT id FROM users")
        self.write_message({
          'cmd' : 'roster', 
          'users' : results.fetchall()
        })

def main():
  port = 8083
  print "Listening on " + str(port) 
  app = Application()
  app.listen(port)
  tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
  main()
