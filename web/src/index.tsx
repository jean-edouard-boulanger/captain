import React, {useEffect, useState} from 'react';
import ReactDOM from 'react-dom/client';
import '@fontsource/roboto';
import useMediaQuery from '@mui/material/useMediaQuery';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import {App} from './App';

const DARK_MODE_SETTING_KEY = "captain.darkMode"


function makeTheme(enableDarkMode: boolean) {
  return createTheme({
    palette: {
      mode: enableDarkMode ? 'dark' : 'light',
    },
  });
}

function isDarkModeUsedByDefault(systemUsesDarkMode: boolean): boolean {
  const localDefault = localStorage.getItem(DARK_MODE_SETTING_KEY);
  if(localDefault === null) {
    return systemUsesDarkMode;
  }
  return localDefault === "1";
}

function setDarkModeDefault(useDarkModeByDefault: boolean) {
  localStorage.setItem(DARK_MODE_SETTING_KEY, useDarkModeByDefault ? "1" : "0");
}

function AppContainer() {
  const [darkMode, setDarkMode] = useState(isDarkModeUsedByDefault(useMediaQuery('(prefers-color-scheme: dark)')));
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

const rootElement = document.getElementById("root");
if(rootElement === null) {
  throw new Error('Failed to find the root element');
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <AppContainer />
  </React.StrictMode>
);
