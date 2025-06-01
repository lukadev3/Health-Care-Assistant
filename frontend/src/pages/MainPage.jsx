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
  const [notifications, setNotifications] = useState([]);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [fileToDelete, setFileToDelete] = useState(null);
  const [chats, setChats] = useState([]);
  const [selectedChat, setSelectedChat] = useState(null);
  const [showChatNameModal, setShowChatNameModal] = useState(false);
  const [newChatName, setNewChatName] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [chatToDelete, setChatToDelete] = useState(null);
  const [editingChatId, setEditingChatId] = useState(null);
  const [editingChatName, setEditingChatName] = useState("");
  const [openDropdown, setOpenDropdown] = useState({
    type: null, 
    index: null
  });


  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatNameInputRef = useRef(null);

  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

  const addNotification = (message, status) => {
    const id = Date.now();
    setNotifications(prev => [...prev, { id, message, status, show: true }]);
    
    setTimeout(() => {
      removeNotification(id);
    }, 5000);
  };

  const removeNotification = (id) => {
    setNotifications(prev => prev.map(n => 
      n.id === id ? { ...n, show: false } : n
    ));
    
    setTimeout(() => {
      setNotifications(prev => prev.filter(n => n.id !== id));
    }, 1000);
  };

  const startEditingChat = (chat) => {
    setEditingChatId(chat.id);
    setEditingChatName(chat.name || "");
    setOpenDropdown({ type: null, index: null });
  };

  const cancelEditingChat = () => {
    setEditingChatId(null);
    setEditingChatName("");
  };

  const saveChatName = async () => {
    if (!editingChatId) return;
    
    const nameToSave = editingChatName.trim() || "Untitled Chat";
    
    try {
      const res = await fetch(`${BACKEND_URL}/chats/${editingChatId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: nameToSave
        }),
      });

      if (!res.ok) throw new Error("Failed to rename chat");

      const data = await res.json();
      const newName = data.chat_name || nameToSave;
      
      setChats(prev => prev.map(chat => 
        chat.id === editingChatId ? { ...chat, name: newName } : chat
      ));
      
      if (selectedChat?.id === editingChatId) {
        setSelectedChat(prev => prev.name === newName ? prev : { ...prev, name: newName });
      }
    } catch (error) {
      console.error("Error renaming chat:", error);
    } finally {
      setEditingChatId(null);
      setEditingChatName("");
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    fetchFiles();
    fetchChats();
  }, []);

  useEffect(() => {
    if (selectedChat) {
      const shouldFetch = messages.length === 0 || 
                        (messages[0] && messages[0].chatId !== selectedChat.id);
      
      if (shouldFetch) {
        setChatLoading(true);
        fetchMessages(selectedChat.id).finally(() => setChatLoading(false));
      }
    } else {
      setMessages([]);
    }
  }, [selectedChat?.id]); 

  const handleDropdownToggle = (type, index, e) => {
    e.stopPropagation();
    e.preventDefault();
    
    if (openDropdown.type === type && openDropdown.index === index) {
      setOpenDropdown({ type: null, index: null });
    } else {
      setOpenDropdown({ type, index });
    }
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.file-options-dropdown, .chat-options-dropdown') && 
          !event.target.closest('.file-options-trigger, .chat-options-trigger')) {
        setOpenDropdown({ type: null, index: null });
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
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
        setMessages([{ text: "Hello! How can I help you today?", sender: "bot", chatId }]);
      } else {
        const formattedMessages = data.messages.flatMap(msg => [
          { text: msg.usermessage, sender: "user", chatId },
          { text: msg.botmessage, sender: "bot", chatId }
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
      addNotification("Chat created successfully.", "success");
    } catch (error) {
      console.error("Error creating chat:", error);
      addNotification("Error creating chat.", "error");
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

      addNotification("Chat deleted successfully.", "success");
    } catch (error) {
      console.error("Error deleting chat:", error);
      addNotification("Error deleting chat.", "success");
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

    try {
      const res = await fetch(`${BACKEND_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error("Upload failed");
      fetchFiles();

      const data = await res.json();
      addNotification(data.message || "File uploaded successfully.", "succes")
    } catch (err) {
      console.error("Error uploading file:", err);
      addNotification("Error uploading file.","error")
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
      fetchFiles();

      const data = await res.json();
      addNotification(data.message || "File deleted successfully.", "succes")
    } catch (err) {
      console.error("Error deleting file:", err);
      addNotification("Error deleting file.","error")
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

      <div className="notification-container">
        {notifications.map((notification) => (
          <div 
            key={notification.id}
            className={`upload-message ${notification.status} ${!notification.show ? "fade-out" : ""}`}
          >
            <span>{notification.message}</span>
            <button 
              className="close-button" 
              onClick={() => removeNotification(notification.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>

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
              className={selectedChat?.id === chat.id ? "active" : ""}
              onClick={(e) => {
                if (!e.target.closest('.chat-options-trigger') && 
                    !e.target.closest('.chat-options-dropdown') &&
                    !e.target.closest('.chat-name-input')) {
                  setSelectedChat(chat);
                }
              }}
            >
              <div className="chat-row">
                {editingChatId === chat.id ? (
                  <input
                    type="text"
                    className="chat-name-input"
                    value={editingChatName}
                    onChange={(e) => setEditingChatName(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveChatName();
                      if (e.key === "Escape") cancelEditingChat();
                    }}
                    onBlur={saveChatName}
                    autoFocus
                  />
                ) : (
                  <span className="chat-name">{chat.name || "Untitled Chat"}</span>
                )}
                <div
                  className="chat-options-trigger"
                  onClick={(e) => handleDropdownToggle('chat', index, e)}
                >
                  ⋯
                </div>
              </div>
              {openDropdown.type === 'chat' && openDropdown.index === index && (
                <div className="chat-options-dropdown">
                  <div
                    className="dropdown-option other-option"
                    onClick={(e) => {
                      e.stopPropagation();
                      startEditingChat(chat);
                    }}
                  >
                    Rename
                  </div>
                  <div
                    className="dropdown-option delete-option"
                    onClick={(e) => {
                      e.stopPropagation();
                      setChatToDelete(chat.id);
                      setOpenDropdown({ type: null, index: null });
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
                <a href={`${BACKEND_URL}/files/${file.filename}`} target="_blank" rel="noopener noreferrer" className="file-link">
                  {file.filename}
                </a>
                <div 
                  className="file-options-trigger"
                  onClick={(e) => handleDropdownToggle('file', index, e)}
                >
                  ⋯
                </div>
              </div>
              {openDropdown.type === 'file' && openDropdown.index === index && (
                <div className="file-options-dropdown">
                  <div 
                    className="dropdown-option delete-option"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFileToDelete(file.filename);
                      setShowDeleteConfirm(true);
                      setOpenDropdown({ type: null, index: null });
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