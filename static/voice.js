// Voice Search + Voice Answer
// Browser ke built-in Web Speech API se — koi API key ya internet service nahi chahiye.
// Best support: Google Chrome.

function nxVoiceSearch() {
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    alert("Voice search isn't supported in this browser. Try Google Chrome.");
    return;
  }
  var input = document.getElementById('nx-q');
  var recognition = new Recognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  input.placeholder = "Listening...";
  recognition.start();

  recognition.onresult = function (event) {
    var text = event.results[0][0].transcript;
    input.value = text;
    input.closest('form').submit();
  };
  recognition.onerror = function () {
    input.placeholder = "Didn't catch that — try again";
  };
}

function nxSpeakTop() {
  if (!window.speechSynthesis) {
    alert("Voice answer isn't supported in this browser.");
    return;
  }
  var first = document.querySelector('.res .item .s') || document.querySelector('.res .s');
  var title = document.querySelector('.res .item .t');
  if (!first) {
    alert("Nothing to read yet.");
    return;
  }
  var text = (title ? title.textContent + ". " : "") + first.textContent;
  window.speechSynthesis.cancel();
  var utter = new SpeechSynthesisUtterance(text);
  utter.lang = 'en-US';
  window.speechSynthesis.speak(utter);
}
