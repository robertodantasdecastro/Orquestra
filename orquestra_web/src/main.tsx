import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { InstallerApp, UninstallerApp } from "./InstallerApps";
import "./styles.css";

const appMode = import.meta.env.VITE_ORQUESTRA_APP_MODE;
const RootApp = appMode === "installer" ? InstallerApp : appMode === "uninstaller" ? UninstallerApp : App;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <RootApp />
  </React.StrictMode>
);
