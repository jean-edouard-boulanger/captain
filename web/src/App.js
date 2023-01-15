import React, {useEffect, useState} from 'react';
import {
  Alert,
  Container,
  IconButton,
  AppBar,
  Toolbar,
  Grid,
  Collapse,
  Snackbar,
  Button,
  Typography
} from '@mui/material'
import ClearIcon from '@mui/icons-material/Clear';
import AddCircleIcon from '@mui/icons-material/AddCircle';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';

import { StartDownload } from './StartDownload';
import { DownloadsTable } from "./DownloadsTable";
import { NotConnected } from "./NotConnected";

import { getServerEndpoint } from './endpoint';
import { ConnectState } from "./domain";
import { Controller } from "./controller";

import './App.css';


function App({toggleDarkMode, darkMode}) {
  const [endpoint] = useState(() => getServerEndpoint());
  const [controller, setController] = useState(null);
  const [connectState, setConnectState] = useState(ConnectState.Disconnect);
  const [settings, setSettings] = useState(null);
  const [downloads, setDownloads] = useState([]);
  const [displayNewTaskForm, setDisplayNewTaskForm] = useState(false);
  const [notification, setNotification] = useState(null);
  const ThemeIcon = darkMode ? LightModeIcon : DarkModeIcon;

  useEffect(() => {
    if(endpoint === null) { return; }
    setController(new Controller({
      endpoint,
      eventHandlers: {
        onConnectionStateChanged: (newState) => {
          setConnectState(newState);
        },
        onRecap: (data) => {
          setSettings(data.settings);
          setDownloads(data.downloads.map(entry => {
            return {
              handle: entry.handle,
              payload: entry
            };
          }));
        },
        onNotification: (data) => {
          setNotification({
            severity: data.payload.severity.toLowerCase(),
            message: data.payload.message,
          });
        },
        onDownloadTaskEvent: (data) => {
          if(data.event_type === "DOWNLOAD_ERRORED") {
            setNotification({
              severity: "error",
              message: data.payload.error_message,
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
        }
      }
    }));
  }, [endpoint]);

  const isConnected = () => {
    return connectState === ConnectState.Connect;
  };

  return (
    <React.Fragment>
      <AppBar title='Captain' color='primary'>
        <Toolbar>
          <Typography type='title' color='inherit' sx={{ flexGrow: 1 }}>
            Captain
          </Typography>
          <IconButton size="large"
                      aria-label="account of current user"
                      aria-controls="menu-appbar"
                      aria-haspopup="true"
                      color="inherit"
                      onClick={toggleDarkMode} >
            <ThemeIcon />
          </IconButton>

        </Toolbar>
      </AppBar>
      <Toolbar />
      <Toolbar />
      <Container maxWidth='lg'>
      {
        (!isConnected()) &&
        <NotConnected currentState={connectState} />
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
                action={
                  <IconButton size="small" aria-label="close" color="inherit" >
                    <ClearIcon fontSize="small" />
                  </IconButton>
                }>
        <Alert elevation={6} severity={(notification ?? {}).severity}>
          {(notification ?? {}).message || ""}
        </Alert>
      </Snackbar>
    </React.Fragment>
  );
}

export default App;
