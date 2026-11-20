import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { VolunteerProvider } from './context/VolunteerContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <VolunteerProvider>
      <App />
    </VolunteerProvider>
  </React.StrictMode>
);
