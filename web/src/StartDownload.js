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

export default function StartDownload({onStart, onCancel, settings}) {
  const [remoteFileUrl, setRemoteFileUrl] = useState(null);
  const [saveTo, setSaveTo] = useState("system-auto");
  const [localDir, setLocalDir] = useState(null);
  const [renameTo, setRenameTo] = useState(null);
  const [authMode, setAuthMode] = useState(null);
  const [credentials, setCredentials] = useState(defaultCredentials())
  const [formErrors, setFormErrors] = useState({})
  const [displayScheduleDialog, setDisplayScheduleDialog] = useState(false);

  useEffect(() => {
    if(saveTo === null) { return; }
    if(saveTo === "system-auto" || saveTo === "system-custom") {
      setLocalDir(null);
      return;
    }
    setLocalDir(saveTo);
  }, [saveTo]);

  const validateForm = (data) => {
    const errors = {}
    if(isBlank(data.remoteFileUrl)) {
      errors.remoteFileUrl = true;
    }
    if(data.saveTo === "system-custom" && isBlank(data.localDir)) {
      errors.localDir = true;
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

  const getFormData = () => {
    const download = {
      remoteFileUrl,
      saveTo,
      localDir,
      renameTo,
      authMode,
      credentials
    };
    const validation = validateForm(download);
    return {
      download,
      ...validation
    };
  }

  const resetForm = () => {
    setRemoteFileUrl(null);
    setSaveTo("system-auto");
    setLocalDir(null);
    setAuthMode(null);
    setCredentials(defaultCredentials());
    setFormErrors({});
  }

  const submitForm = ({schedule}) => {
    const formData = getFormData()
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
  }

  const initSchedule = () => {
    const formData = getFormData()
    if(!formData.valid) {
      setFormErrors(formData.errors);
    }
    else
    {
      setDisplayScheduleDialog(true);
    }
  }

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
                          value={saveTo || "system-auto"}
                          onChange={(event) => {
                            setSaveTo(event.target.value)
                          }} >
                    <MenuItem value="system-auto">Automatic</MenuItem>
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
                    <MenuItem value="system-custom">Custom</MenuItem>
                  </Select>
                </FormControl>
              </Box>
              <Box m={1} flexGrow={1} hidden={saveTo === "system-auto"}>
                <TextField label="Directory"
                           value={localDir || ""}
                           error={formErrors.localDir !== undefined}
                           onChange={(e) => {setLocalDir(e.target.value)}}
                           disabled={saveTo !== "system-custom"}
                           fullWidth />
              </Box>
            </Box>
          </Grid>
          <Grid item>
            <Box m={1}>
              <TextField label="Rename file to"
                         value={renameTo || ""}
                         onChange={(e) => {setRenameTo(e.target.value)}}
                         fullWidth />
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
                           value={credentials.username} />
              </Box>
              <Box m={1} hidden={authMode !== "basic"}>
                <TextField label="Password"
                           type="password"
                           error={formErrors.password !== undefined}
                           onChange={(e) => {
                             credentials.password = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.password}/>
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
