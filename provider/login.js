function toSignup() {
  showPage("signup-page");
}

function login() {
  var form = document.getElementsByTagName('form')[0];
  form.addEventListener('submit', function(e) {
    e.preventDefault();
    var credentials = {
        user: form.user.value,
        password: form.password.value,
        action: 'login'
    };
    parent.postMessage(credentials, '*');  
    return false;
  }, true);
}

function showPage(id) {
  console.log("show page: " + id);
  var pg = document.getElementById(id);
  if (!pg) {
    alert("no such page");
    return;
  }

  // get all pages, loop through them and hide them
  var pages = document.getElementsByClassName('page');
  for(var i = 0; i < pages.length; i++) 
      pages[i].style.display = 'none';

  pg.style.display = 'block';
}

window.onload = function() {
  showPage("login-page");

  var form = document.getElementsByTagName('form')[1];
  form.addEventListener('submit', function(e) {
    e.preventDefault();
    var newUser = {
      user: form.user.value,
      password: form.password.value,
      action: 'signup'
    };
    parent.postMessage(newUser, '*');
    showPage("login-page");      
    document.getElementById('status').innerText = "successfully signed up";
    return false;
  }, true);


  window.addEventListener('message', function(m) {
    document.getElementById('status').innerText = m.data;
  }, true);
} 