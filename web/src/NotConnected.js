import React from 'react';
import {
  Card,
  Grid,
  CardContent,
  Typography,
} from "@material-ui/core";
import PortableWifiOffIcon from '@material-ui/icons/PortableWifiOff';


export function NotConnected({connection}) {
  return (
    <Card>
      <CardContent>
        <Grid container direction="row" alignItems="center" spacing={1} style={{marginBottom: '0.8em'}}>
          <Grid item>
            <PortableWifiOffIcon color={"primary"} />
          </Grid>
          <Grid item>
            <Typography variant="h5" component="h2">
              Not connected to Captain server ({connection})
            </Typography>
          </Grid>
        </Grid>
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
