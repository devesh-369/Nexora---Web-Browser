// Free weather widget — uses the browser's own location + Open-Meteo
// (no API key, no sign-up needed). Only runs when the user clicks the button.

function nxGetWeather() {
  var body = document.getElementById('weather-body');
  if (!body) return;
  if (!navigator.geolocation) {
    body.innerHTML = '<div class="ask-note">Geolocation is not supported in this browser.</div>';
    return;
  }
  body.innerHTML = '<div class="ask-note">Getting your location…</div>';

  navigator.geolocation.getCurrentPosition(function (pos) {
    var lat = pos.coords.latitude, lon = pos.coords.longitude;
    fetch('/weather?lat=' + lat + '&lon=' + lon)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) {
          body.innerHTML = '<div class="ask-note">' + d.error + '</div>';
          return;
        }
        body.innerHTML =
          '<div style="font-size:30px;font-weight:700">' + d.temp + '°C</div>' +
          '<div class="s" style="color:#cfd5e8;margin-top:4px">' + d.condition + ' · ' + d.city + '</div>';
      })
      .catch(function () {
        body.innerHTML = '<div class="ask-note">Could not fetch weather right now.</div>';
      });
  }, function () {
    body.innerHTML = '<div class="ask-note">Location permission denied.</div>';
  });
}
