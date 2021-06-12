import React from 'react';
import {
  Card,
  CardContent,
  Typography,
} from "@material-ui/core";


export function NotConnected({connection}) {
  return (
    <Card>
      <CardContent>
        <Typography gutterBottom variant="h5" component="h2">
          Not connected to Captain server ({connection})
        </Typography>
        <Typography variant="body1">
          We were unable to connect to Captain server, there are a few reasons why this could be:
        </Typography>
        <ul>
          <li>Is it currently running?</li>
          <li>Is it properly configured?</li>
        </ul>
      </CardContent>
    </Card>
  );
}
