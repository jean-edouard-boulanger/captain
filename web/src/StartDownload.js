import React, {useEffect, useState} from 'react';
import {
  Button,
  Card,
  CardActions,
  CardContent,
  TextField,
  Typography,
  FormControl,
  FormHelperText,
  Select,
  MenuItem,
  Collapse,
  Grid
} from "@material-ui/core";


function isBlank(val) {
  return val === "" || val === null || val === undefined;
}

function defaultCredentials() {
  return {username: null, password: null};
}

export default function StartDownload({onStart, onCancel, settings}) {
  const [remoteFileUrl, setRemoteFileUrl] = useState(null);
  const [localDir, setLocalDir] = useState(null);
  const [authMode, setAuthMode] = useState(null);
  const [credentials, setCredentials] = useState(defaultCredentials())
  const [formErrors, setFormErrors] = useState({})

  useEffect(() => {
    if(settings === null) { return; }
    if(localDir === null) {
      setLocalDir(settings.default_download_dir);
    }
  }, [settings, localDir])

  const validateForm = () => {
    const errors = {}
    if(isBlank(remoteFileUrl)) {
      errors.remoteFileUrl = true;
    }
    if(authMode === "simple") {
      if(isBlank(credentials.username)) {
        errors.username = true
      }
      if(isBlank(credentials.password)) {
        errors.password = true
      }
    }
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  }

  const getFormData = () => {
    return {
      remoteFileUrl,
      localDir,
      authMode,
      credentials
    };
  }

  const resetForm = () => {
    setRemoteFileUrl(null);
    setLocalDir(null);
    setAuthMode(null);
    setCredentials(defaultCredentials());
    setFormErrors({});
  }

  const submitForm = () => {
    if(validateForm()) {
      const formData = getFormData();
      resetForm();
      onStart(formData);
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
            <TextField value={remoteFileUrl || ""}
                       label="Remote file URL"
                       error={formErrors.remoteFileUrl !== undefined}
                       onChange={(e) => {setRemoteFileUrl(e.target.value)}}
                       fullWidth />
          </Grid>
          <Grid item>
            <TextField label="Save to"
                       value={localDir || ""}
                       onChange={(e) => {setLocalDir(e.target.value)}}
                       fullWidth />
          </Grid>
          <Grid item>
            <FormControl>
              <FormHelperText>Authentication mode</FormHelperText>
              <Select value={authMode || "none"}
                      onChange={(e) => setAuthMode(e.target.value)}>
                <MenuItem value="none">None</MenuItem>
                <MenuItem value="basic">Basic</MenuItem>
              </Select>
            </FormControl>
          </Grid>
          <Grid item>
            <Collapse in={authMode === "basic"}>
                <TextField label="Username"
                           error={formErrors.username !== undefined}
                           onChange={(e) => {
                             credentials.username = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.username} />
                <TextField label="Password"
                           type="password"
                           error={formErrors.password !== undefined}
                           onChange={(e) => {
                             credentials.password = e.target.value;
                             setCredentials({...credentials});
                           }}
                           value={credentials.password}/>
            </Collapse>
          </Grid>
        </Grid>
      </CardContent>
      <CardActions>
        <Button size="small" onClick={() => submitForm()}>
          Start
        </Button>
        <Button size="small" onClick={() => onCancel()}>
          Cancel
        </Button>
      </CardActions>
    </Card>
  );
}