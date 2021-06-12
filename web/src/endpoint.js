export function getServerEndpoint() {
  const endpoint = process.env.REACT_APP_CAPTAIN_SERVER_ENDPOINT;
  if(endpoint !== undefined) {
    return endpoint;
  }
  return "127.0.0.1:5001";
}
