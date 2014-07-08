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
import shelve
import hashlib

class Application(tornado.web.Application):
  def __init__(self):
    handlers = [(r"/route/([a-zA-Z0-9_]*)", MainHandler)]
    #handlers = [(r"/route", MainHandler)]
    settings = dict( autoescape=None )
    tornado.web.Application.__init__(self, handlers, **settings)

class MainHandler(tornado.websocket.WebSocketHandler):
  users = shelve.open('users.db')
  waiters = dict()  #userid => WebSocketHandler
  sites = dict()    #origin => [userids]

  def allow_draft76(self):
    return True

  #def open(self):
  #  self.setup(self.request.headers.get("Origin"))
  
  def open(self, app_id):
    if (app_id == None or app_id == ''):
      app_id = self.request.headers.get("Origin")
    self.setup(app_id)
    
  # Setup a new connection
  def setup(self, site):
    self.sites = [site]

    if not site in MainHandler.sites:
      MainHandler.sites[site] = []

  def on_finish(self):
    self.on_close()
  
  # Close connection
  def on_close(self):
    if hasattr(self, 'id'):
      # Cleanup global state
      for key in self.sites:
        MainHandler.sites[key].remove(self.id)
      del MainHandler.waiters[self.id]
    # Broadcast user has left
    if self.id and self.sites:
      for site in self.sites:
        for user in MainHandler.sites[site]:
          MainHandler.waiters[user].write_message({
            'cmd': "roster",
            'id': self.id,
            'online': False
          });

  # On incoming message
  def on_message(self, msg):
    val = tornado.escape.json_decode(msg)
    if not self.id and 'cmd' in val and val['cmd'] == 'login':
      if 'user' in val and 'password' in val and user['val'] in MainHandler:
        user = MainHandler[val['user']]
        if hashlib.sha256(val['password'] + user['salt']) == val['hash']:
          self.id = val['user']
          return
      return self.write_message({'error': 'invalid login'})
    elif not self.id and 'cmd' in val and val['cmd'] == 'register':
      if 'user' in val and 'password' in val and val['user'] not in MainHandler \
          and len(val['user']) > 3 and len(val['user']) < 20 and len(val['password']) > 3:
        salt = os.urandom(16)
        newhash = hashlib.sha256(val['password'] + salt)
        MainHandler[val['user']] = {'salt': salt, 'hash': newhash}
        return
      return self.write_message({'error': 'invalid login'})
    elif not self.id:
      return self.write_message({'error': 'not logged in'})

    val['cmd'] = "message";
    val['from'] = self.id

    # Check across all sites
    for s in self.sites:
      val['site'] = s
      # If recipient is specified, find that connection
      if 'to' in val:
        if val['to'] in MainHandler.sites[s]:
          MainHandler.waiters[val['to']].write_message(val)
      # If no recipient, broadcast to all in that site
      else:
        for u in MainHandler.sites[s]:
          if u != self.id:
            MainHandler.waiters[u].write_message(val)

def main():
  port = 8082
  print "Listening on " + str(port) 
  app = Application()
  app.listen(port)
  tornado.ioloop.IOLoop.instance().start()

if __name__ == "__main__":
  main()
