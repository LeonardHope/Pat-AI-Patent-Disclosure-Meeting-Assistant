import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/globals.css";
import "./demo"; // Register demo mode (window.__loadDemo())

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
