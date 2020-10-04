import React from 'react';
import {
  Card,
  CardContent,
  Typography,
} from "@material-ui/core";


export default function NotConnected({connection}) {
  return (
    <Card>
      <CardContent>
        <Typography gutterBottom variant="h5" component="h2">
          Not connected to Captain server ({connection})
        </Typography>
        <Typography variant="body1">
          <p>We were unable to connect to Captain server, there are a few reasons why this could be:</p>
          <ul>
            <li>Is it currently running?</li>
            <li>Is it properly configured?</li>
          </ul>
        </Typography>
      </CardContent>
    </Card>
  );
}
