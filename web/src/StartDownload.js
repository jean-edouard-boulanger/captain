import React, {useEffect, useState} from 'react';
import {
  Button,
  Box,
  ListSubheader,
  Card,
  CardActions,
  CardContent,
  Divider,
  TextField,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid
} from "@material-ui/core";
import ScheduleDialog from "./ScheduleDialog";


function isBlank(val) {
  return val === "" || val === null || val === undefined;
}


function defaultCredentials() {
  return {username: null, password: null};
}

const CUSTOM_DOWNLOAD_DIR_SELECTION = "system-custom";

function getDefaultDownloadLocation(settings) {
  if(settings.download_directories.length === 0) {
    return CUSTOM_DOWNLOAD_DIR_SELECTION
  }
  return settings.download_directories[0].directory
}

export function StartDownload({onStart, onCancel, settings, controller}) {
  const [remoteFileUrl, setRemoteFileUrl] = useState(null);
  const [saveTo, setSaveTo] = useState(() => {
    return getDefaultDownloadLocation(settings)
  });
  const [downloadDir, setDownloadDir] = useState(null);
  const [authMode, setAuthMode] = useState(null);
  const [credentials, setCredentials] = useState(defaultCredentials())
  const [formErrors, setFormErrors] = useState({})
  const [displayScheduleDialog, setDisplayScheduleDialog] = useState(false);

  useEffect(() => {
    if(isBlank(saveTo)) { return; }
    if(saveTo === CUSTOM_DOWNLOAD_DIR_SELECTION) {
      setDownloadDir(null);
      return;
    }
    setDownloadDir(saveTo);
  }, [saveTo]);

  const validateForm = async (data) => {
    const errors = {}
    if(isBlank(data.remoteFileUrl)) {
      errors.remoteFileUrl = true;
    }
    if(data.saveTo === CUSTOM_DOWNLOAD_DIR_SELECTION && isBlank(data.downloadDir)) {
      errors.downloadDir = true;
    }
    if(!isBlank(data.downloadDir)) {
      const {valid, reason} = await controller.validateDirectory(data.downloadDir);
      if(!valid) {
        errors.downloadDir = reason;
      }
    }
    if(data.authMode === "simple") {
      if(isBlank(data.credentials.username)) {
        errors.username = true
      }
      if(isBlank(data.credentials.password)) {
        errors.password = true
      }
    }
    return {
      errors,
      valid: Object.keys(errors).length === 0
    }
  }

  const getFormData = async () => {
    const download = {
      remoteFileUrl,
      saveTo,
      downloadDir,
      authMode,
      credentials
    };
    const validation = await validateForm(download);
    return {
      download,
      ...validation
    };
  };

  const resetForm = () => {
    setRemoteFileUrl(null);
    setSaveTo(getDefaultDownloadLocation(settings));
    setDownloadDir(null);
    setAuthMode(null);
    setCredentials(defaultCredentials());
    setFormErrors({});
  };

  const submitForm = async ({schedule}) => {
    const formData = await getFormData();
    if(!formData.valid) {
      setFormErrors(formData.errors);
    }
    else {
      resetForm();
      onStart({
        download: formData.download,
        schedule: schedule || null
      });
    }
  };

  const initSchedule = async () => {
    const formData = await getFormData();
    if(!formData.valid) {
      setFormErrors(formData.errors);
    }
    else
    {
      setDisplayScheduleDialog(true);
    }
  };

  useEffect(() => {
    setFormErrors({})
  }, [remoteFileUrl, saveTo, downloadDir, authMode, credentials]);

  return (
    <Card>
      <CardContent>
        <Typography gutterBottom variant="h5" component="h2">
          New Task
        </Typography>
        <Grid container direction="column" spacing={2}>
          <Grid item>
            <Box m={1}>
            <TextField value={remoteFileUrl || ""}
                       label="Remote file URL"
                       error={formErrors.remoteFileUrl !== undefined}
                       onChange={(e) => {setRemoteFileUrl(e.target.value)}}
                       fullWidth />
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex">
              <Box m={1}>
                <FormControl style={{minWidth: 200}}>
                  <InputLabel id="save-to-select-label">Save to</InputLabel>
                  <Select labelId="save-to-select-label"
                          value={saveTo}
                          onChange={(event) => {
                            setSaveTo(event.target.value)
                          }} >
                    {
                      (settings !== null) &&
                      [
                        <ListSubheader>Presets</ListSubheader>,
                        settings.download_directories.map((entry) => {
                          return (
                            <MenuItem value={entry.directory}>{entry.label}</MenuItem>
                          )
                        })
                      ]
                    }
                    <ListSubheader><Divider /></ListSubheader>,
                    <MenuItem value={CUSTOM_DOWNLOAD_DIR_SELECTION}>Custom</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} flexGrow={1}>
                <TextField label="Directory"
                           value={downloadDir || ""}
                           error={formErrors.downloadDir !== undefined}
                           onChange={(e) => {setDownloadDir(e.target.value)}}
                           helperText={formErrors.downloadDir || ""}
                           disabled={saveTo !== CUSTOM_DOWNLOAD_DIR_SELECTION}
                           fullWidth />
              </Box>
            </Box>
          </Grid>
          <Grid item>
            <Box display="flex">
              <Box m={1}>
                <FormControl style={{minWidth: 200}}>
                  <InputLabel id="auth-mode-select-label">Authentication</InputLabel>
                  <Select labelId="auth-mode-select-label"
                          value={authMode || "none"}
                          onChange={(e) => setAuthMode(e.target.value)}>
                    <MenuItem value="none">None</MenuItem>
                    <MenuItem value="basic">Basic</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} hidden={authMode !== "basic"}>
                <TextField label="Username"
                           error={formErrors.username !== undefined}
                           onChange={(e) => {
                             credentials.username = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.username || ""} />
              </Box>
              <Box m={1} hidden={authMode !== "basic"}>
                <TextField label="Password"
                           type="password"
                           error={formErrors.password !== undefined}
                           onChange={(e) => {
                             credentials.password = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.password || ""}/>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
      <CardActions>
        <Button size="small" onClick={() => submitForm({schedule: null})}>
          Start
        </Button>
        <Button size="small" onClick={() => initSchedule()}>
          Schedule
        </Button>
        <Button size="small" onClick={() => {resetForm(); onCancel()}}>
          Cancel
        </Button>
      </CardActions>
      <ScheduleDialog open={displayScheduleDialog}
                      onClose={(schedule) => {
                        submitForm({schedule})
                        setDisplayScheduleDialog(false);
                      }} />
    </Card>
  );
}
