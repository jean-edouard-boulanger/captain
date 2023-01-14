import React, {useEffect, useState} from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import '@fontsource/roboto';
import useMediaQuery from '@mui/material/useMediaQuery';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

const DARK_MODE_SETTING_KEY = "captain.darkMode"


function makeTheme(darkMode) {
  return createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
    },
  });
}

function getDarkModeDefault(systemUsesDarkByDefault) {
  const localDefault = localStorage.getItem(DARK_MODE_SETTING_KEY);
  if(localDefault === "0" || localDefault === null) {
    return false;
  }
  return systemUsesDarkByDefault;
}

function setDarkModeDefault(useDarkModeByDefault) {
  localStorage.setItem(DARK_MODE_SETTING_KEY, useDarkModeByDefault ? "1" : "0");
}

function AppContainer() {
  const [darkMode, setDarkMode] = useState(getDarkModeDefault(useMediaQuery('(prefers-color-scheme: dark)')));
  const [theme, setTheme] = useState(makeTheme(darkMode));

  useEffect(() => {
    setDarkModeDefault(darkMode);
    setTheme(makeTheme(darkMode));
  }, [darkMode])

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App toggleDarkMode={() => setDarkMode(!darkMode)} darkMode={darkMode} />
    </ThemeProvider>
  )
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <AppContainer />
  </React.StrictMode>
);
