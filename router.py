#!/usr/bin/env python
"""
Websocket rendezvous with persistent accounts.
Listens on http://localhost:8082/route
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
    #handlers = [(r"/route", MainHandler)]
    settings = dict( autoescape=None )
    tornado.web.Application.__init__(self, handlers, **settings)

class MainHandler(tornado.websocket.WebSocketHandler):
  #users = sqlite3.connect('users.db')
  test = sqlite3.connect('test.db')
  f = open('test.sql', 'r')
  sql = f.read()
  test.executescript(sql)

  waiters = dict()  #userid => WebSocketHandler
  msg_dict = dict() #pendingMsgs 

  def allow_draft76(self):
    return True

  #def open(self):
  #  self.setup(self.request.headers.get("Origin"))
  
  def open(self, app_id):
    if (app_id == None or app_id == ''):
      app_id = self.request.headers.get("Origin")
    #self.setup(app_id)
    
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
            cur = MainHandler.test.cursor()
            cur.execute("INSERT INTO users VALUES('" + val['user'] + "','" + val['password'] + "')")
    elif val['cmd'] == 'login':
      with MainHandler.test: 
            cur = MainHandler.test.cursor()
            query = '''SELECT password FROM users 
            WHERE id=?
            ''' 
            results = cur.execute(query, [val['user']])

            login_success = False

            for r in results.fetchall(): 
              if str(r[0]) == val['password']: 
                login_success = True
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
            if login_success is False: 
                self.write_message({
                  'error': 'invalid login'
                })

    elif val['cmd'] == 'send':
      to = val['to']
      if to in MainHandler.waiters: 
        MainHandler.waiters[to].write_message({ #goes to social.mb.js, onMessage
          'msg' : val['msg'],
          'cmd' : 'send'
        })
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

    #if not self.id and 'cmd' in val and val['cmd'] == 'login':
     # if 'user' in val and 'password' in val and user['val'] in MainHandler.user:
      #  user = MainHandler.user[val['user']]
       # if hashlib.sha256(val['password'] + user['salt']) == val['hash']:
        #  self.id = val['user']
         # return
      #return self.write_message({'error': 'invalid login'})
    #elif not self.id and 'cmd' in val and val['cmd'] == 'register':
     # if 'user' in val and 'password' in val and val['user'] not in MainHandler \
      #    and len(val['user']) > 3 and len(val['user']) < 20 and len(val['password']) > 3:
       # salt = os.urandom(16)
        #newhash = hashlib.sha256(val['password'] + salt)
        #MainHandler[val['user']] = {'salt': salt, 'hash': newhash}
        #return
     # return self.write_message({'error': 'invalid login'})
    # elif not self.id:
      # return self.write_message({'error': 'not logged in'})

   # val['cmd'] = "message";
    # val['from'] = self.id

def main():
  port = 8083
  print "Listening on " + str(port) 
  app = Application()
  app.listen(port)
  tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
  main()
