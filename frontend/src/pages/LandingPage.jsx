import { useNavigate } from 'react-router-dom';
import AnimatedPage from '../components/AnimatedPages';
import './LandingPage.css';

export default function App() {
  const navigate = useNavigate();

  return (
    <AnimatedPage>
      <div id='content'>
        <h1>Welcome to Health-Care Assistant!</h1>
        <h2>AI-Powered Assistant for Smarter Patient Care.</h2>
        <button onClick={() => navigate("/main")}>Start</button>
      </div>
    </AnimatedPage>
  );
}