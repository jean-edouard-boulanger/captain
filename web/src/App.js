import React, {useEffect, useState} from 'react';
import {
  Container,
  IconButton,
  AppBar,
  Toolbar,
  Grid,
  Collapse,
  Snackbar,
  Button,
  Typography
} from '@material-ui/core'
import MuiAlert from '@material-ui/lab/Alert';
import ClearIcon from '@material-ui/icons/Clear';
import AddCircleIcon from '@material-ui/icons/AddCircle';
import socketIOClient from 'socket.io-client'

import { StartDownload } from './StartDownload';
import { DownloadsTable } from "./DownloadsTable";
import { NotConnected } from "./NotConnected";

import { getServerEndpoint } from './endpoint';
import { makeController } from "./Controller";

import './App.css';


const ConnectState = {
  CONNECT: "connected",
  CONNECTING: "connecting",
  DISCONNECT: "disconnected",
  CONNECT_FAILED: "connection failed",
  RECONNECT: "connected",
  RECONNECTING: "connecting",
  RECONNECT_FAILED: "connection failed"
}


function Alert(props) {
  return <MuiAlert elevation={6} variant="filled" {...props} />;
}


function App() {
  const [endpoint] = useState(() => getServerEndpoint());
  const [socket, setSocket] = useState(null);
  const [controller, setController] = useState(null);
  const [connectState, setConnectState] = useState(ConnectState.DISCONNECT);
  const [settings, setSettings] = useState(null);
  const [downloads, setDownloads] = useState([]);
  const [displayNewTaskForm, setDisplayNewTaskForm] = useState(false);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    const newSocket = socketIOClient(endpoint);
    setSocket(newSocket);
    setController(makeController({ endpoint, socket: newSocket }))
  }, [endpoint]);

  useEffect(() => {
    if(socket === null) { return; }
    socket.on("connect", () => { setConnectState(ConnectState.CONNECT); });
    socket.on("connecting", () => { setConnectState(ConnectState.CONNECTING); });
    socket.on("disconnect", () => { setConnectState(ConnectState.DISCONNECT); });
    socket.on("connect_failed", () => { setConnectState(ConnectState.CONNECT_FAILED); });
    socket.on("reconnect", () => { setConnectState(ConnectState.CONNECT); });
    socket.on("reconnecting", () => { setConnectState(ConnectState.RECONNECTING); });
    socket.on("reconnect_failed", () => { setConnectState(ConnectState.RECONNECT_FAILED); });

    socket.on("recap", data => {
      setSettings(data.settings);
      setDownloads(data.downloads.map(entry => {
        return {
          handle: entry.handle,
          payload: entry
        };
      }));
    });

    socket.on("download_event", data => {
      if(data.event_type === "GENERAL_NOTIFICATION") {
        setNotification({
          message: data.payload.message,
          severity: data.payload.severity.toLowerCase()
        });
        return;
      }
      if(data.event_type === "DOWNLOAD_ERRORED") {
        setNotification({
          message: data.payload.state.error_info.message,
          severity: "error"
        })
      }
      setDownloads(current => {
        const newDownloads = [...current];
        let existing = false;
        newDownloads.forEach(entry => {
          if (entry.handle === data.payload.handle) {
            entry.payload = data.payload;
            existing = true;
          }
        });
        if(!existing) {
          newDownloads.push({
            handle: data.payload.handle,
            payload: data.payload
          })
        }
        return newDownloads;
      });
    });
  }, [socket]);

  const isConnected = () => {
    return connectState === ConnectState.CONNECT;
  };

  return (
    <React.Fragment>
      <AppBar title='Captain' color='primary'>
        <Toolbar>
          <Typography type='title' color='inherit'>
            Captain
          </Typography>
        </Toolbar>
      </AppBar>
      <Toolbar />
      <Toolbar />
      <Container maxWidth='lg'>
      {
        (!isConnected()) &&
        <NotConnected connection={connectState} />
      }
      {
        (isConnected()) &&
        <React.Fragment>
          <Collapse in={!displayNewTaskForm}>
            <Grid item xs={12}>
              <Button variant="contained"
                      startIcon={<AddCircleIcon />}
                      onClick={() => setDisplayNewTaskForm(true)} >
                New Task
              </Button>
            </Grid>
          </Collapse>
          <Collapse in={displayNewTaskForm}>
            <Grid item xs={12}>
              <StartDownload onStart={(data) => {
                               setDisplayNewTaskForm(false);
                               controller.startDownload(data);
                             }}
                             onCancel={() => setDisplayNewTaskForm(false)}
                             settings={settings}
                             controller={controller} />
            </Grid>
          </Collapse>
          <Grid item xs={12}>
            <DownloadsTable downloads={downloads}
                            controller={controller}
                            settings={settings} />
          </Grid>
        </React.Fragment>
      }
      </Container>
      <Snackbar anchorOrigin={{vertical: 'bottom', horizontal: 'left'}}
                open={notification !== null}
                onClose={() => setNotification(null)}
                autoHideDuration={(notification ?? {}).autoHideDuration}
                action={
                  <IconButton size="small" aria-label="close" color="inherit" >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                }>
        <Alert severity={(notification ?? {}).severity || "info"} >
          {(notification ?? {}).message || ""}
        </Alert>
      </Snackbar>
    </React.Fragment>
  );
}

export default App;
