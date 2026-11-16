import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AppProvider } from "./ctx";
import { ToastProvider } from "./components/Toast";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><AppProvider><ToastProvider><App /></ToastProvider></AppProvider></BrowserRouter></React.StrictMode>
);
