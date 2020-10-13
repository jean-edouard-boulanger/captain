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

import StartDownload from './StartDownload';
import DownloadsTable from "./DownloadsTable";
import NotConnected from "./NotConnected";

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


function getServerEndpoint() {
  const endpoint = process.env.REACT_APP_CAPTAIN_SERVER_ENDPOINT;
  if(endpoint !== undefined) {
    return endpoint;
  }
  return "http://127.0.0.1:5001";
}


function makeController(socket) {
  return {
    pauseDownload: (handle) => {
      socket.emit("pause_download", {"handle": handle})
    },
    resumeDownload: (handle) => {
      socket.emit("resume_download", {"handle": handle})
    },
    stopDownload: (handle) => {
      socket.emit("stop_download", {"handle": handle})
    },
    retryDownload: (handle) => {
      socket.emit("retry_download", {"handle": handle})
    },
    rescheduleDownload: (handle, startAt) => {
      socket.emit("reschedule_download", {
        "handle": handle,
        "start_at": startAt.toISOString()
      })
    },
    removeDownload: (handle) => {
      socket.emit("remove_download", {"handle": handle})
    },
    startDownload: (data) => {
      const download = data.download;
      const makeAuth = () => {
        if(download.authMode === "none" || download.authMode === null)
        {
          return null;
        }
        let auth = {};
        auth[download.authMode] = download.credentials;
        return auth;
      };
      const makeStartAt = () => {
        if(data.schedule === null) {
          return null;
        }
        return data.schedule.toISOString()
      };
      socket.emit("start_download", {
        remote_file_url: download.remoteFileUrl,
        local_dir: download.localDir,
        local_file_name: download.renameTo,
        start_at: makeStartAt(),
        auth: makeAuth()
      });
    }
  }
}

function App() {
  const [socket, setSocket] = useState(null);
  const [controller, setController] = useState(null);
  const [connectState, setConnectState] = useState(ConnectState.DISCONNECT);
  const [settings, setSettings] = useState(null);
  const [downloads, setDownloads] = useState([]);
  const [displayNewTaskForm, setDisplayNewTaskForm] = useState(false);
  const [notification, setNotification] = useState(null);

  useEffect(() => {
    setSocket(socketIOClient(getServerEndpoint()));
  }, []);

  useEffect(() => {
    if(socket === null) { return; }
    setController(makeController(socket));
  }, [socket])

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
          severity: data.payload.severity
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
                             settings={settings} />
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
