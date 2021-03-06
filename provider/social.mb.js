/*globals freedom:true, WebSocket, DEBUG */
/*jslint indent:2, white:true, node:true, sloppy:true, browser:true */

/**
 * Implementation of a Social provider that persists data in
 * the server-side router.py
 * The current implementation uses a public facing server
 * hosted on p2pbr.com
 *
 * The provider offers registration and limited queuing of messages
 * for delayed delivery. All registered users are visible to all other users.
 * @class WSSocialProvider
 * @constructor
 * @param {Function} dispatchEvent callback to signal events
 * @param {WebSocket} webSocket Alternative webSocket implementation for tests
 **/

function WSSocialProvider(dispatchEvent, webSocket) {
  this.dispatchEvent = dispatchEvent;

  this.websocket = freedom["core.websocket"] || webSocket;
  if (typeof DEBUG !== 'undefined' && DEBUG) {
    this.WS_URL = 'ws://localhost:8083/mailbox/';
  } else {
    this.WS_URL = 'wss://p2pbr.com/mailbox/';
  }
  this.social = freedom.social();
  this.view = freedom['core.view']();

  this.conn = null;   // Web Socket
  this.id = null;     // userId of this user
  
  this.users = {};    // List of seen users (<user_profile>)
  this.clients = {};  // List of seen clients (<client_state>)
}

/**
 * Begin login by asking the user for credentials.
 *
 * @method login
 * @param {Object} loginOptions
 * @return {Object} status - Same schema as 'onStatus' events
 **/
WSSocialProvider.prototype.login = function(loginOpts, continuation) {
  // Wrap the continuation so that it will only be called once.
  var finishLogin = {
    continuation: continuation,
    finish: function(msg, err) {
      if (this.continuation) {
        this.continuation(msg, err);
        delete this.continuation;
        return true;
      } else {
        return false;
      }
    }
  };

  if (this.conn !== null) {
    finishLogin.finish(undefined, this.err("LOGIN_ALREADYONLINE"));
    return;
  }
  this.conn = this.websocket(this.WS_URL + loginOpts.agent);

  this.conn.on("onMessage", this.onMessage.bind(this, finishLogin));
  this.conn.on("onError", function (cont, error) {
    this.conn = null;
    cont.finish(undefined, this.err('ERR_CONNECTION')) ||
        this.changeRoster(this.id, false);
  }.bind(this, finishLogin));
  this.conn.on("onClose", function (cont, msg) {
    this.conn = null;
    this.changeRoster(this.id, false);
  }.bind(this, finishLogin));


  if(loginOpts.interactive) {
    this.view.on('message', this.onLogin.bind(this));
    this.view.open('login', {file: 'login.html'}).then(this.view.show.bind(this.view));
  } else { 
    this.conn.on("onOpen", function(cont, msg) {
      // TODO: support non-interactive logins without overloading url param.
      var parts = loginOpts.url.split(':');
      this.conn.send({text: JSON.stringify({
        cmd: 'login',
        user: parts[0],
        password: parts[1]
      })});
    }.bind(this, finishLogin));  
  }
};

/**
 * Returns all the <user_profile>s that we've seen so far (from 'onUserProfile' events)
 * Note: the user's own <user_profile> will be somewhere in this list. 
 * Use the userId returned from social.login() to extract your element
 * NOTE: This does not guarantee to be entire roster, just users we're currently aware of at the moment
 * e.g. social.getUsers();
 *
 * @method getUsers
 * @return {Object} { 
 *    'userId1': <user_profile>,
 *    'userId2': <user_profile>,
 *     ...
 * } List of <user_profile>s indexed by userId
 *   On failure, rejects with an error code (see above)
 **/
WSSocialProvider.prototype.getUsers = function(continuation) {
  if (this.conn === null) {
    continuation(undefined, this.err("OFFLINE"));
    return;
  }
  continuation(this.users);
};

/**
 * Returns all the <client_state>s that we've seen so far (from any 'onClientState' event)
 * Note: this instance's own <client_state> will be somewhere in this list
 * Use the clientId returned from social.login() to extract your element
 * NOTE: This does not guarantee to be entire roster, just clients we're currently aware of at the moment
 * e.g. social.getClients()
 * 
 * @method getClients
 * @return {Object} { 
 *    'clientId1': <client_state>,
 *    'clientId2': <client_state>,
 *     ...
 * } List of <client_state>s indexed by clientId
 *   On failure, rejects with an error code (see above)
 **/
WSSocialProvider.prototype.getClients = function(continuation) {
  if (this.conn === null) {
    continuation(undefined, this.err("OFFLINE"));
    return;
  }
  continuation(this.clients);
};

/** 
 * Send a message to user on your network
 * If the destination is not specified or invalid, the message is dropped
 * Note: userId and clientId are the same for this.websocket
 * e.g. sendMessage(String destination_id, String message)
 * 
 * @method sendMessage
 * @param {String} destination_id - target
 * @return nothing
 **/
WSSocialProvider.prototype.sendMessage = function(to, msg, continuation) {
  if (this.conn === null) {
    continuation(undefined, this.err("OFFLINE"));
    return;
  } else if (!this.clients.hasOwnProperty(to) && !this.users.hasOwnProperty(to)) {
    console.warn('Invalid destination', to);
    continuation(undefined, this.err("SEND_INVALIDDESTINATION"));
    return;
  }

  //send to router
  this.conn.send({text: JSON.stringify({cmd: 'send', to: to, msg: msg})});
  continuation();
};

/**
 * Disconnects from the Web Socket server
 * e.g. logout(Object options)
 * No options needed
 * 
 * @method logout
 * @return {Object} status - same schema as 'onStatus' events
 **/
WSSocialProvider.prototype.logout = function(continuation) {
  if (this.conn === null) { // We may not have been logged in
    this.changeRoster(this.id, false);
    continuation(undefined, this.err("OFFLINE"));
    return;
  }
  this.conn.on("onClose", function(continuation) {
    this.conn = null;
    this.changeRoster(this.id, false);
    continuation();
  }.bind(this, continuation));
  this.conn.close();
};

/**
 * INTERNAL METHODS
 **/

/**
 * Dispatch an 'onClientState' event with the following status and return the <client_card>
 * Modify entries in this.users and this.clients if necessary.
 * Because the router knows all clients & states we use that DB.
 *
 * @method changeRoster
 * @private
 * @param {String} id - userId and clientId are the same in this provider
 * @param {Boolean} stat - true if "ONLINE", false otherwise
 * @return {Object} - same schema as 'onStatus' event
 **/
WSSocialProvider.prototype.changeRoster = function(id, stat) {
  var newStatus, result = {
    userId: id,
    clientId: id,
    lastUpdated: (this.clients.hasOwnProperty(id)) ? this.clients[id].lastUpdated: (new Date()).getTime(),
    lastSeen: (new Date()).getTime()
  };
  if (stat) {
    newStatus = "ONLINE";
  } else {
    newStatus = "OFFLINE";
  }
  result.status = newStatus;
  if (!this.clients.hasOwnProperty(id) || 
      (this.clients[id] && this.clients[id].status !== newStatus)) {
    this.dispatchEvent('onClientState', result);
  }

  if (stat) {
    this.clients[id] = result;
    if (!this.users.hasOwnProperty(id)) {
      this.users[id] = {
        userId: id,
        name: id,
        lastUpdated: (new Date()).getTime()
      };
      this.dispatchEvent('onUserProfile', this.users[id]);
    }
  } else {
    delete this.users[id];
    delete this.clients[id];
  }
  return result;
};

/**
 * Handle messages from the server
 * There are 3 types of messages
 * - Actual messages from friends.
 * - Notifications of new users on the server.
 * - Responses to login / signup requests.
 *
 * @method onMessage
 * @private
 * @param {String} msg Message from the server (see router.py for the other side)
 **/
WSSocialProvider.prototype.onMessage = function(finish, msg) {
  //from router.py, on_message (write_message)
  var i, msg;
  try {
    msg = JSON.parse(msg.text);
  } catch(e) {
    console.warn('Unparseable message from server', msg.text);
    return;
  }

  // Emit actual messages
  if (msg.cmd === 'message') {
    this.dispatchEvent('onMessage', {
      from: this.changeRoster(msg.from, true),
      message: msg.msg
    });
  // Roster Updates.
  } else if (msg.cmd === 'roster') {
    for (var i = 0; i < msg.users.length; i++)
      this.dispatchEvent ('onUserProfile', { //main.js, social.on(onUserProfile)
        'userId' : msg.users[i]
      });
    //this.changeRoster(msg.id, msg.online);
  // Finish logging in.
  } else if(msg.cmd == 'login') {
    this.view.close(); 

    this.conn.send({text: JSON.stringify({cmd: 'get_users'})});

    this.id = msg.user;
    this.changeRoster(msg.user, true);
    var ret = {
      'userId': msg.user, 
      'clientId': msg.user,
      'status': 'ONLINE',
      'timestamp': (new Date()).getTime()
    };

    finish.finish(ret);
  }
};

/**
 * Handle requests from the user login view.
 *
 * @param {Object} msg The message sent from the view.
 */
WSSocialProvider.prototype.onLogin = function(msg) {
  //from login.js
  if (msg.action === "login"){ 
    this.conn.send({text: JSON.stringify({cmd: 'login', user: msg.user, password: msg.password})});
    //goes to router.py, on_message
  } else if (msg.action == 'signup') {
    this.conn.send({text: JSON.stringify({cmd: 'register', user: msg.user, password: msg.password})});
    //goes to router.py, on_message
  }
};

WSSocialProvider.prototype.err = function(code) {
  var err = {
    errcode: code,
    message: this.social.ERRCODE[code]
  };
  return err;
};

/** REGISTER PROVIDER **/
if (typeof freedom !== 'undefined') {
  freedom.social().provideAsynchronous(WSSocialProvider);
}
