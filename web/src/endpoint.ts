export function getServerEndpoint(): string {
  const endpoint = process.env.REACT_APP_CAPTAIN_SERVER_ENDPOINT;
  if(endpoint !== undefined) {
    return endpoint;
  }
  return "http://127.0.0.1:4001";
}
