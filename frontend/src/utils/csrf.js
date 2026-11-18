export function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  if (match) {
    return decodeURIComponent(match[1]);
  }
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return input ? input.value : '';
}
