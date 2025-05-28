import { useState, useRef, useEffect } from "react";
import "./MainPage.css";
import ReactMarkdown from "react-markdown";

function TypingIndicator() {
  return (
    <div className="typing-indicator">
      <span className="dot" />
      <span className="dot" />
      <span className="dot" />
    </div>
  );
}

function MainPage() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadStatus, setUploadStatus] = useState("success");
  const [showFadeOut, setShowFadeOut] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [fileToDelete, setFileToDelete] = useState(null);
  const [fileDropdownIndex, setFileDropdownIndex] = useState(null);
  const [chats, setChats] = useState([]);
  const [selectedChat, setSelectedChat] = useState(null);
  const [showChatNameModal, setShowChatNameModal] = useState(false);
  const [newChatName, setNewChatName] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatToDelete, setChatToDelete] = useState(null);
  const [chatDropdownIndex, setChatDropdownIndex] = useState(null);

  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const dropdownRef = useRef(null);
  const chatNameInputRef = useRef(null);

  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetchFiles();
    fetchChats();
  }, []);

  useEffect(() => {
    if (selectedChat) {
      setChatLoading(true);
      fetchMessages(selectedChat.id).finally(() => setChatLoading(false));
    } else {
      setMessages([]);
    }
  }, [selectedChat]);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setFileDropdownIndex(null);
        setChatDropdownIndex(null);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const fetchFiles = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/files`);
      const data = await res.json();
      setUploadedFiles(data.files);
    } catch (error) {
      console.error("Failed to fetch files:", error);
    }
  };

  const fetchChats = async () => {
    try {
      setChatLoading(true);
      const res = await fetch(`${BACKEND_URL}/chats`);
      const data = await res.json();
      setChats(data.chats);
      
      if (data.chats.length > 0 && !selectedChat) {
        setSelectedChat(data.chats[0]);
      }
    } catch (error) {
      console.error("Failed to fetch chats:", error);
    } finally {
      setChatLoading(false);
    }
  };

  const fetchMessages = async (chatId) => {
    try {
      const res = await fetch(`${BACKEND_URL}/chats/${chatId}/messages`);
      const data = await res.json();
      
      if (data.messages.length === 0) {
        setMessages([{ text: "Hello! How can I help you today?", sender: "bot" }]);
      } else {
        const formattedMessages = data.messages.flatMap(msg => [
          { text: msg.usermessage, sender: "user" },
          { text: msg.botmessage, sender: "bot" }
        ]);
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error("Failed to fetch messages:", error);
    }
  };

  const handleCreateChat = async () => {
    setShowChatNameModal(true);
    setTimeout(() => chatNameInputRef.current?.focus(), 100);
  };

  const confirmCreateChat = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/chats`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newChatName || undefined
        }),
      });

      if (!res.ok) throw new Error("Failed to create chat");

      const data = await res.json();
      const newChat = { id: data.chat_id, name: data.chat_name };
      
      setChats(prev => [...prev, newChat]);
      setSelectedChat(newChat);
      setShowChatNameModal(false);
      setNewChatName("");
    } catch (error) {
      console.error("Error creating chat:", error);
      setUploadStatus("error");
      setUploadMessage("Error creating chat.");
      setTimeout(() => setUploadMessage(""), 3000);
    }
  };

  const confirmDeleteChat = async () => {
    try {
      setChatLoading(true);
      await fetch(`${BACKEND_URL}/chats/${chatToDelete}`, {
        method: "DELETE"
      });
      
      setChats(prev => prev.filter(chat => chat.id !== chatToDelete));
      
      if (selectedChat?.id === chatToDelete) {
        const remainingChats = chats.filter(chat => chat.id !== chatToDelete);
        setSelectedChat(remainingChats.length > 0 ? remainingChats[0] : null);
      }

      setUploadStatus("success");
      setUploadMessage("Chat deleted successfully.");
      setTimeout(() => setShowFadeOut(true), 5000);
      setTimeout(() => {
        setUploadMessage("");
        setShowFadeOut(false);
      }, 6000);
    } catch (error) {
      console.error("Error deleting chat:", error);
      setUploadStatus("error");
      setUploadMessage("Error deleting chat.");
      setTimeout(() => setShowFadeOut(true), 5000);
      setTimeout(() => {
        setUploadMessage("");
        setShowFadeOut(false);
      }, 6000);
    } finally {
      setChatLoading(false);
      setChatToDelete(null);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || !selectedChat) return;

    const userMessage = { text: input, sender: "user" };
    setMessages(prev => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    const typingMessage = { text: "Typing...", sender: "bot" };
    setMessages(prev => [...prev, typingMessage]);

    try {
      await fetch(`${BACKEND_URL}/chats/${selectedChat.id}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          usermessage: input,
          botmessage: ""
        }),
      });

      const res = await fetch(
        `${BACKEND_URL}/query?q=${encodeURIComponent(input)}&id=${selectedChat.id}`,
        { method: "GET", mode: "cors" }
      );

      if (!res.ok) throw new Error(await res.text());

      const data = await res.json();
      const botMessage = { text: data.response, sender: "bot" };

      await fetch(`${BACKEND_URL}/chats/${selectedChat.id}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          usermessage: input,
          botmessage: data.response
        }),
      });

      setMessages(prev => {
        const updated = [...prev];
        updated.pop();
        updated.push(botMessage);
        return updated;
      });
    } catch (error) {
      console.error("Error:", error);
      setMessages(prev => [
        ...prev.filter(m => m.text !== "Typing..."),
        { text: "Error contacting server.", sender: "bot" },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    setUploading(true);
    setUploadMessage("");
    setUploadStatus("success");
    setShowFadeOut(false);

    try {
      const res = await fetch(`${BACKEND_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");

      const data = await res.json();
      setUploadStatus("success");
      setUploadMessage(data.message || "File uploaded successfully.");
      fetchFiles();

      setTimeout(() => setShowFadeOut(true), 5000);
      setTimeout(() => {
        setUploadMessage("");
        setShowFadeOut(false);
      }, 6000);
    } catch (err) {
      console.error("Error uploading file:", err);
      setUploadStatus("error");
      setUploadMessage("Error uploading file.");

      setTimeout(() => setShowFadeOut(true), 5000);
      setTimeout(() => {
        setUploadMessage("");
        setShowFadeOut(false);
      }, 6000);
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (filename) => {
    const formData = new FormData();
    const fileBlob = new Blob([], { type: "application/pdf" });
    const fakeFile = new File([fileBlob], filename);
    formData.append("file", fakeFile);

    try {
      setUploading(true);
      const res = await fetch(`${BACKEND_URL}/delete`, {
        method: "DELETE",
        body: formData,
      });

      if (!res.ok) throw new Error("Failed to delete file");

      const data = await res.json();
      setUploadStatus("success");
      setUploadMessage(data.message || "File deleted successfully.");
      fetchFiles();

      setTimeout(() => setShowFadeOut(true), 5000);
      setTimeout(() => {
        setUploadMessage("");
        setShowFadeOut(false);
      }, 6000);
    } catch (err) {
      console.error("Error deleting file:", err);
      setUploadStatus("error");
      setUploadMessage("Error deleting file.");

      setTimeout(() => setShowFadeOut(true), 5000);
      setTimeout(() => {
        setUploadMessage("");
        setShowFadeOut(false);
      }, 6000);
    } finally {
      setUploading(false);
      setShowDeleteConfirm(false);
      setFileToDelete(null);
    }
  };

  return (
    <div id="chat_content">
      {uploading && (
        <div className="overlay">
          <div className="spinner" />
        </div>
      )}

      {chatLoading && (
        <div className="overlay">
          <div className="spinner" />
        </div>
      )}

      {uploadMessage && (
        <div className={`upload-message ${uploadStatus} ${showFadeOut ? "fade-out" : ""}`}>
          <span>{uploadMessage}</span>
          <button className="close-button" onClick={() => setUploadMessage("")}>
            ×
          </button>
        </div>
      )}

      {showChatNameModal && (
        <div className="delete-confirm-modal">
          <div className="modal-content">
            <h3>Name your chat</h3>
            <input
              ref={chatNameInputRef}
              type="text"
              value={newChatName}
              onChange={(e) => setNewChatName(e.target.value)}
              placeholder="Enter chat name (optional)"
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmCreateChat();
              }}
            />
            <div className="modal-buttons">
              <button
                className="create-button" 
                onClick={confirmCreateChat}
              >
                Create
              </button>
              <button 
                className="cancel-button"
                onClick={() => {
                setShowChatNameModal(false);
                setNewChatName("");
              }}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {chatToDelete && (
        <div className="delete-confirm-modal">
          <div className="modal-content">
            <p>Are you sure you want to delete this chat?</p>
            <div className="modal-buttons">
              <button
                className="yes-button"
                onClick={() => {
                  confirmDeleteChat();
                }}
              >
                Yes
              </button>
              <button
                className="cancel-button"
                onClick={() => {
                  setChatToDelete(null);
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeleteConfirm && fileToDelete && (
        <div className="delete-confirm-modal">
          <div className="modal-content">
            <p>Are you sure you want to delete <strong>{fileToDelete}</strong>?</p>
            <div className="modal-buttons">
              <button
                className="yes-button"
                onClick={() => {
                  handleDeleteFile(fileToDelete);
                }}
              >
                Yes
              </button>
              <button
                className="cancel-button"
                onClick={() => {
                  setShowDeleteConfirm(false);
                  setFileToDelete(null);
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <aside className="sidebar">
        <div className="section-header">
          <h3>Chats</h3>
          <button className="action-button" onClick={handleCreateChat}>
            + New Chat
          </button>
        </div>
        <ul className="chat-history">
          {chats.map((chat, index) => (
            <li
              key={chat.id}
              className={selectedChat?.id === chat.id ? "active" : "inactive"}
              onClick={() => setSelectedChat(chat)}
            >
              <div className="chat-row">
                <span className="chat-name">{chat.name || "Untitled Chat"}</span>
                <div
                  className="chat-options-trigger"
                  onClick={(e) => {
                    e.stopPropagation();
                    setChatDropdownIndex(chatDropdownIndex === index ? null : index);
                  }}
                >
                  ⋯
                </div>
              </div>
              {chatDropdownIndex === index && (
                <div className="chat-options-dropdown" ref={dropdownRef}>
                  <div
                    className="dropdown-option"
                    onClick={(e) => {
                      e.stopPropagation();
                      setChatToDelete(chat.id);
                      setChatDropdownIndex(null);
                    }}
                  >
                    🗑 Delete
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      </aside>
      <main className="chat-center">
        {selectedChat ? (
          <div className="chat-window">
            <div className="chat-header">
              <h3>{selectedChat.name}</h3>
            </div>
            <div className="messages">
              {messages.map((msg, idx) => (
                <div key={idx} className={`message ${msg.sender}`}>
                  {msg.text === "Typing..." ? (
                    <TypingIndicator />
                  ) : (
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                  )}
                </div>
              ))}
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
                style={{
                  opacity: isLoading ? 0.5 : 1,
                  cursor: isLoading ? "not-allowed" : "pointer",
                }}
              >
                {isLoading ? "Generating..." : "Send"}
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-chat">
            <h2>Manual Assistance</h2>
            <p>Select a chat or create a new one to start messaging</p>
          </div>
        )}
      </main>

      <aside className="file-panel">
        <div className="section-header">
          <h3>Files</h3>
          <button
            className="action-button"
            onClick={() => fileInputRef.current.click()}
          >
            + Upload File
          </button>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: "none" }}
            onChange={handleFileUpload}
          />
        </div>
        <ul>
          {uploadedFiles.map((file, index) => (
            <li key={index} className="file-item">
              <div className="file-row">
                <a
                  href={`${BACKEND_URL}/files/${file.filename}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="file-link"
                >
                  {file.filename}
                </a>
                <div
                  className="file-options-trigger"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFileDropdownIndex(fileDropdownIndex === index ? null : index);
                  }}
                >
                  ⋯
                </div>
              </div>
              {fileDropdownIndex === index && (
                <div className="file-options-dropdown" ref={dropdownRef}>
                  <div
                    className="dropdown-option"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFileToDelete(file.filename);
                      setShowDeleteConfirm(true);
                      setFileDropdownIndex(null);
                    }}
                  >
                    🗑 Delete
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}

export default MainPage;