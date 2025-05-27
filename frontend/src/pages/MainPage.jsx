import { useState } from 'react';
import { useRef, useEffect } from 'react';
import './MainPage.css';
import ReactMarkdown from 'react-markdown';

function MainPage() {
  const [messages, setMessages] = useState([
    { text: "Hello! How can I help you today?", sender: "bot" },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false)
  
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);


  const handleSend = async () => {
    if (!input.trim()) return;

    setIsLoading(true);
    const userMessage = { text: input, sender: "user" };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");

    // Dodaj "Typing..." indikator
    let typingMessage = { text: "Typing...", sender: "bot" };
    setMessages((prev) => [...prev, typingMessage]);

    try {

      const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;
      const response = await fetch(`${BACKEND_URL}/query?q=${encodeURIComponent(input)}`, {
        method: "GET",
        mode: "cors"
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }

      const data = await response.json(); 

      const botMessage = { text: data.response, sender: "bot" };

      setMessages((prev) => {
        const updated = [...prev];
        updated.pop(); 
        updated.push(botMessage);
        return updated;
      });
    } catch (error) {
      console.error("Error:", error);
      setMessages((prev) => [
        ...prev.filter((m) => m.text !== "Typing..."),
        { text: "Error contacting server.", sender: "bot" },
      ]);
    } finally{
      setIsLoading(false);
    }
  };


  return (
    <>
      <div id='chat_content'>
        <aside className="sidebar">
             <div className="section-header">
                <h3>Chats</h3>
                <button className="action-button">+ New Chat</button>
            </div>
            <ul className="chat-history">
                <li>Chat 1</li>
                <li>Chat 2</li>
            </ul>
        </aside>

        <main className="chat-center">
            <div className="chat-window">
            <div className="messages">
              {messages.map((msg, idx) => {
                return (
                  <div key={idx} className={`message ${msg.sender}`}>
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
            <div className="input-area">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !isLoading) handleSend();
                  }}
                  placeholder="Type your message..."
                />
                <button
                onClick={handleSend}
                disabled={isLoading}
                style={{ opacity: isLoading ? 0.5 : 1, cursor: isLoading ? 'not-allowed' : 'pointer' }}
                >
                {isLoading ? "Generating..." : "Send"}
                </button>
              </div>
            </div>
        </main>

        <aside className="file-panel">
             <div className="section-header">
                <h3>Files</h3>
                <button className="action-button">+ Upload File</button>
            </div>
            <ul>
                <li>example.pdf</li>
                <li>invoice.docx</li>
            </ul>
        </aside>
      </div>
    </>
  );
}

export default MainPage;
