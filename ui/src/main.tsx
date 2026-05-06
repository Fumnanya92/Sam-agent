import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/globals.css";
import "./styles/brutalist.css";
import "./styles/shell.css";
import "./styles/brutalist-overrides.css";

const root = createRoot(document.getElementById("root")!);
root.render(<App />);
