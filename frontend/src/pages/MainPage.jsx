import { useState, useRef, useEffect, useCallback } from "react";
import "./MainPage.css";
import ReactMarkdown from "react-markdown";
import remarkGfm from 'remark-gfm'
import { Copy, Pencil, Search, FileCheck } from 'lucide-react';
import { EditableTextArea } from "../components/EditableTextArea";
import CustomInputArea from '../components/CustomInputArea';

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
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [showEvaluationModal, setShowEvaluationModal] = useState(false);
  const [groundTruth, setGroundTruth] = useState("");
  const [currentEvalIndex, setCurrentEvalIndex] = useState(null);
  const [isSearchLoading, setIsSearchLoading] = useState(false);
  const [searchType, setSearchType] = useState(null); 
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [allMessages, setAllMessages] = useState([]);
  const [messages, setMessages] = useState([]);
  const [originalMessage, setOriginalMessage] = useState([]);
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
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [loadingMessageIndex, setLoadingMessageIndex] = useState(0);
  const [evaluationResult, setEvaluationResult] = useState(null); 
  
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatNameInputRef = useRef(null);
  const groundTruthInputRef = useRef(null);
  const shouldScrollRef = useRef(true);
  const inputRef = useRef();
  const loadingMessages = [
    "Analyzing answer...",
    "Comparing ground truth...",
    "Measuring semantic similarity...",
    "Consulting LLM...",
    "Almost done..."
  ];
  const evaluationKeys = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"];

  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

  const highlightText = (text, query) => {
    if (!query || !text) return text;
    
    const queryLower = query.toLowerCase();
    const textLower = text.toLowerCase();
    const index = textLower.indexOf(queryLower);

    if (index === -1) return text;
    
    const prefix = index > 20 ? '...' : '';
    const displayText = index > 20 ? text.slice(index - 20) : text;
    
    const parts = displayText.split(new RegExp(`(${query})`, 'gi'));
    return (
      <>
        {prefix}
        {parts.map((part, i) => 
          part.toLowerCase() === queryLower ? 
          <span key={i} className="highlight">{part}</span> : 
          part
        )}
      </>
    );
  };

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

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to rename chat");
      }

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
      addNotification(error.message || "Error renaming chat", "error");
    } finally {
      setEditingChatId(null);
      setEditingChatName("");
    }
  };

  useEffect(() => {
    if (shouldScrollRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
    shouldScrollRef.current = true;
  }, [messages]);

  useEffect(() => {
    fetchFiles();
    fetchChats();
    fetchAllMessages();
  }, []);

  useEffect(() => {
    if (selectedChat) {
      setChatLoading(true);
      setMessages([]);
      fetchMessages(selectedChat.id).finally(() => setChatLoading(false));
    } else {
      setMessages([]);
    }
  }, [selectedChat?.id]);

  useEffect(() => {
    let interval;
    if (isEvaluating) {
      setLoadingMessageIndex(0); 
      interval = setInterval(() => {
        setLoadingMessageIndex((prev) => {
          if (prev < loadingMessages.length - 1) {
            return prev + 1;
          } else {
            clearInterval(interval); 
            return prev;
          }
        });
      }, 18000); 
    }
    return () => clearInterval(interval); 
  }, [isEvaluating]);


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
        
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || "Failed to fetch files");
        }

        const data = await res.json();
        setUploadedFiles(data.files);
    } catch (error) {
        console.error("Failed to fetch files:", error);
        addNotification(error.message || "Failed to load files", "error");
    }
  };

  const fetchChats = async () => {
    try {
        setChatLoading(true);
        const res = await fetch(`${BACKEND_URL}/chats`);
        
        if (!res.ok) {
            const errorData = await res.json();
            throw new Error(errorData.error || "Failed to fetch chats");
        }

        const data = await res.json();
        setChats(data.chats);
        
        if (data.chats.length > 0 && !selectedChat) {
            setSelectedChat(data.chats[0]);
        }
    } catch (error) {
        console.error("Failed to fetch chats:", error);
        addNotification(error.message || "Failed to load chats", "error");
    } finally {
        setChatLoading(false);
    }
  };

  const fetchMessages = async (chatId) => {
    try {
      const res = await fetch(`${BACKEND_URL}/chats/${chatId}/messages`);
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to fetch messages");
      }

      const data = await res.json();
      
      if (data.messages.length > 0) {
        const formattedMessages = data.messages.flatMap(msg => [
          { text: msg.usermessage, sender: "user", chatId, id: msg.id},
          { text: msg.botmessage, sender: "bot", chatId, id: msg.id }
        ]);
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error("Failed to fetch messages:", error);
      addNotification(error.message || "Failed to load chat messages", "error");
      setMessages([{ text: "Failed to load messages. Please try again.", sender: "bot", chatId }]);
    }
  };

  const fetchAllMessages = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/chats/messages`);
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to fetch all messages");
      }
      const data = await res.json();
      setAllMessages(data["all messages"] || []);
    } catch (error) {
      console.error("Failed to fetch all messages:", error);
      addNotification(error.message || "Failed to load messages for search", "error");
    }
  };

  useEffect(() => {
    if (!showSearchModal) return;
    setIsSearchLoading(true);


    const timer = setTimeout(async () => {
      if (!searchQuery.trim()) {
        if (searchType === 'files') {
          setSearchResults(uploadedFiles.map(file => ({
            type: 'file',
            filename: file.filename,
            id: file.filename
          })));
        } else {
          setSearchResults(chats.map(chat => ({
            type: 'chat-list', 
            chatId: chat.id,
            chatName: chat.name,
            id: chat.id
          })));
        }
        setIsSearchLoading(false);
        return;
      }

      const query = searchQuery.toLowerCase();
      
      await new Promise(resolve => setTimeout(resolve, 500));
      
      if (searchType === 'chats') {

        const results = allMessages.filter(msg => 
          msg.usermessage.toLowerCase().includes(query) || 
          msg.botmessage.toLowerCase().includes(query)
        );
        
        setSearchResults(results.map(msg => ({
          type: 'chat-message', 
          chatId: msg.chat_id,
          userMessage: msg.usermessage,
          botMessage: msg.botmessage,
          id: msg.id,
          highlightText: query
        })));
      } else if (searchType === 'files') {
        const results = uploadedFiles.filter(file => 
          file.filename.toLowerCase().includes(query)
        );
        
        setSearchResults(results.map(file => ({
          type: 'file',
          filename: file.filename,
          id: file.filename,
          highlightText: query
        })));
      }
      setIsSearchLoading(false);
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, searchType, showSearchModal, allMessages, uploadedFiles, chats]);

  const openSearchModal = useCallback((type) => {
    setSearchType(type);
    setSearchQuery("");
    setIsSearchLoading(true);
    
    if (type === 'files') {
      setSearchResults(uploadedFiles.map(file => ({
        type: 'file',
        filename: file.filename,
        id: file.filename
      })));
    } else {
      setSearchResults(chats.map(chat => ({
        type: 'chat-list',
        chatId: chat.id,
        chatName: chat.name,
        id: chat.id
      })));
    }
    
    setIsSearchLoading(false);
    setShowSearchModal(true);
  }, [uploadedFiles, chats]);

  const handleSearchResultClick = async (result) => {
    if (result.type === 'chat-list') {
      const chat = chats.find(c => c.id === result.chatId);
      if (chat) {
        setSelectedChat(chat);
        setShowSearchModal(false);
      }
    } else if (result.type === 'chat-message') {
      const chat = chats.find(c => c.id === result.chatId);
      if (chat) {
        setSelectedChat(chat);
        setChatLoading(true);
        
        try {
          shouldScrollRef.current = false;
          
          const res = await fetch(`${BACKEND_URL}/chats/${chat.id}/messages`);
          if (!res.ok) throw new Error("Failed to fetch messages");
          
          const data = await res.json();
          const formattedMessages = data.messages.flatMap(msg => [
            { 
              text: msg.usermessage, 
              sender: "user", 
              chatId: chat.id, 
              id: msg.id,
              isHighlighted: msg.id === result.id
            },
            { 
              text: msg.botmessage, 
              sender: "bot", 
              chatId: chat.id, 
              id: msg.id,
              isHighlighted: msg.id === result.id
            }
          ]);
          
          setMessages(formattedMessages);
          
          setTimeout(() => {
            const highlightedElement = document.querySelector(`.message-wrapper.highlighted`);
            if (highlightedElement) {
              highlightedElement.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'center' 
              });
              const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                  if (entry.isIntersecting) {
                    entry.target.classList.add('flash-effect');
                    
                    setTimeout(() => {
                      entry.target.classList.remove('flash-effect');
                    }, 2000);
                    
                    observer.unobserve(entry.target);
                  }
                });
              }, { threshold: 0.5 });
              
              observer.observe(highlightedElement);
            }
            shouldScrollRef.current = true;
          }, 100);
          
        } catch (error) {
          console.error("Error loading chat messages:", error);
          addNotification(error.message, "error");
        } finally {
          setChatLoading(false);
          setShowSearchModal(false);
        }
      }
    } else if (result.type === 'file') {
      window.open(`${BACKEND_URL}/files/${result.filename}`, '_blank');
      setShowSearchModal(false);
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

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to create chat");
      }

      const data = await res.json();
      const newChat = { id: data.chat_id, name: data.chat_name };
      
      setChats(prev => [...prev, newChat]);
      setSelectedChat(newChat);
      setShowChatNameModal(false);
      setNewChatName("");
      addNotification("Chat created successfully.", "success");
    } catch (error) {
      console.error("Error creating chat:", error);
      addNotification(error.message || "Error creating chat.", "error");
    }
  };

  const confirmDeleteChat = async () => {
    try {
      setChatLoading(true);
      const res = await fetch(`${BACKEND_URL}/chats/${chatToDelete}`, {
        method: "DELETE"
      });
      
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to delete chat");
      }

      setChats(prev => prev.filter(chat => chat.id !== chatToDelete));

      setMessages(prev => {
        if (selectedChat?.id === chatToDelete) {
          return [];
        }
        return prev.filter(msg => msg.chatId !== chatToDelete);
      });

      setAllMessages(prev => prev.filter(msg => msg.chat_id !== chatToDelete));
      
      if (selectedChat?.id === chatToDelete) {
        const remainingChats = chats.filter(chat => chat.id !== chatToDelete);
        setSelectedChat(remainingChats.length > 0 ? remainingChats[0] : null);
      }

      addNotification("Chat deleted successfully.", "success");
    } catch (error) {
      console.error("Error deleting chat:", error);
      addNotification(error.message || "Error deleting chat.", "error");
    } finally {
      setChatLoading(false);
      setChatToDelete(null);
    }
  };  

  const handleSend = async () => {
    if (!input.trim() || !selectedChat) return;

    const userText = input;
    const backupMessages = [...messages]; 
    setInput("");
    setIsLoading(true);

    const tempUserMessage = { text: userText, sender: "user" };
    setMessages(prev => [...prev, tempUserMessage]);

    const typingMessage = { text: "Typing...", sender: "bot" };
    setMessages(prev => [...prev, typingMessage]);

    try {
      const res = await fetch(
        `${BACKEND_URL}/query?q=${encodeURIComponent(userText)}&id=${selectedChat.id}`,
        { method: "GET", mode: "cors" }
      );

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to get response");
      }

      const data = await res.json();

      const saveRes = await fetch(`${BACKEND_URL}/chats/${selectedChat.id}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          usermessage: userText,
          botmessage: data.response,
          context: data.context
        }),
      });

      if (!saveRes.ok) {
        const errorData = await saveRes.json();
        throw new Error(errorData.error || "Failed to save message");
      }

      const postData = await saveRes.json();
      const messageId = postData.id;

      setAllMessages(prev => [...prev, {
        chat_id: selectedChat.id,
        usermessage: userText,
        botmessage: data.response,
        context: data.context,
        id: messageId
      }]);

      setMessages(prev => {
        const updated = [...prev];
        updated.pop(); 

        const userMessage = {
          text: userText,
          sender: "user",
          chatId: selectedChat.id,
          id: messageId,
        };

        const botMessage = {
          text: data.response,
          sender: "bot",
          chatId: selectedChat.id,
          id: messageId,
        };

        updated.pop();
        return [...updated, userMessage, botMessage];
      });
    } catch (error) {
      console.error("Error:", error);
      setMessages(backupMessages)
      addNotification(error.message || "Error generating response", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const saveEditedMessage = async (idx) => {

    const backupMessages = messages.map((msg, i) => {
      if (i === idx) {
        return { ...msg, text: originalMessage, isEditing: false };
      }
      return msg;
    });

    const msg = messages[idx];
    if (!msg.id || !msg.chatId) {
      console.error("Message id or chatId missing");
      return;
    }

    try {
      if (originalMessage.trim() === messages[idx].text.trim()) {
        setMessages(prev => {
          const updated = [...prev];
          if (updated[idx]) {
            updated[idx].isEditing = false;
            updated[idx].text = originalMessage
          }
          return updated;
        });
        return;
      }
      setIsLoading(true);

      setMessages(prev => {
        const updated = [...prev];
        if (updated[idx]) {
          updated[idx].isEditing = false;
        }
        return updated;
      });

      setMessages(prevMessages => {
        const updatedMessages = [...prevMessages];
        const messageIndex = updatedMessages.findIndex(m => m.id === msg.id);
        if (messageIndex !== -1) {
          return updatedMessages.slice(0, messageIndex + 1);
        }
        return updatedMessages;
      });

      const typingMessage = { text: "Typing...", sender: "bot" };
      setMessages(prev => [...prev, typingMessage]);


      const deleteRes = await fetch(`${BACKEND_URL}/chats/${msg.chatId}/messages`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ id: msg.id }),
      });

      if (!deleteRes.ok) {
        const errorData = await deleteRes.json();
        throw new Error(errorData.error || "Failed to delete subsequent messages");
      }

      const res = await fetch(
        `${BACKEND_URL}/query?q=${encodeURIComponent(msg.text)}&id=${msg.chatId}`,
        { method: "GET", mode: "cors" }
      );

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to get response");
      }

      const data = await res.json();

      const saveRes = await fetch(`${BACKEND_URL}/chats/${msg.chatId}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          usermessage: msg.text,
          botmessage: data.response,
          context: data.context 
        }),
      });

      if (!saveRes.ok) {
        const errorData = await saveRes.json();
        throw new Error(errorData.error || "Failed to save edited message");
      }

      const savedData = await saveRes.json();
      const newId = savedData.id;

      setAllMessages(prev => {
        const filtered = prev.filter(m => m.id !== msg.id);
        return [...filtered, {
          chat_id: msg.chatId,
          usermessage: msg.text,
          botmessage: data.response,
          context: data.context,
          id: newId
        }];
      });

      setMessages(prev => {
        const updated = prev.filter(
          m => m.id !== msg.id && m.text !== "Typing..."
        );

        const userMessage = {
          text: msg.text,
          sender: "user",
          chatId: msg.chatId,
          id: newId,
          isEditing: false, 
        };

        const botMessage = {
          text: data.response,
          sender: "bot",
          chatId: msg.chatId,
          id: newId,
        };

        return [...updated, userMessage, botMessage];
      });

    } catch (error) {
      console.error("Error saving edited message:", error);
      setMessages(backupMessages);
      addNotification(error.message || "Error saving edited message", "error");
    } finally {
      setIsLoading(false);
    }
  };

  const openEvaluateModal = (idx) => {
    setCurrentEvalIndex(idx);
    setShowEvaluationModal(true);
    setGroundTruth(""); 
    setTimeout(() => {
      groundTruthInputRef.current?.focus();
    }, 100);
  };

  const evaluateAnswer = async (idx) => {
    setIsEvaluating(true);
    setEvaluationResult(null); 

    try {
      const msg = allMessages[idx];

      if (!msg.id || !msg.chat_id) {
        throw new Error("Message id or chat_id is missing");
      }

      const payload = {
        question: msg.usermessage,
        context: msg.context,
        answer: msg.botmessage,
        ground_truth: groundTruth
      };

      console.log(payload)

      const res = await fetch(`${BACKEND_URL}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to get evaluation");
      }

      const data = await res.json();
      setEvaluationResult(data.evaluation);
    } catch (err) {
      console.error("Evaluation error:", err);
      addNotification(err.message || "Error evaluating message.", "error");
    } finally {
      setIsEvaluating(false);
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

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Upload failed");
      }

      fetchFiles();
      const data = await res.json();
      addNotification(data.message || "File uploaded successfully.", "success");
    } catch (err) {
      console.error("Error uploading file:", err);
      addNotification(err.message || "Error uploading file.", "error");
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

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || "Failed to delete file");
      }

      fetchFiles();
      const data = await res.json();
      addNotification(data.message || "File deleted successfully.", "success");
    } catch (err) {
      console.error("Error deleting file:", err);
      addNotification(err.message || "Error deleting file.", "error");
    } finally {
      setUploading(false);
      setShowDeleteConfirm(false);
      setFileToDelete(null);
    }
  };

  const copyToClipboard = (text) => {
  navigator.clipboard.writeText(text)
    .then(() => {
      addNotification("Text copied to clipboard!", "success");
    })
    .catch((err) => {
      console.error("Failed to copy:", err);
      addNotification("Failed to copy text", "error");
    });
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
                if (e.key === "Escape") {
                  setShowChatNameModal(false);
                  setNewChatName("");
                }
              }}
              className="name-chat-input"
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
            <input
              type="text"
              style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  confirmDeleteChat();
                } else if (e.key === 'Escape') {
                  setChatToDelete(null);
                }
              }}
            />
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
            <input
              type="text"
              style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleDeleteFile(fileToDelete);
                } else if (e.key === 'Escape') {
                  setShowDeleteConfirm(false);
                  setFileToDelete(null);
                }
              }}
            />
          </div>
        </div>
      )}
      {showSearchModal && (
        <div className="delete-confirm-modal">
          <div className="modal-content search-modal">
            <h3>Search {searchType === 'chats' ? 'Chats' : 'Files'}</h3>
            <div className="search-input-container">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={`Search ${searchType === 'chats' ? 'chat messages' : 'files'}...`}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    setShowSearchModal(false);
                  }
                }}
              />
            </div>
            <div className="search-results">
              {isSearchLoading ? (
                <div className="loading-spinner">Loading...</div>
              ) : searchResults.length > 0 ? (
                searchResults.map((result, index) => (
                  <div 
                    key={index} 
                    className="search-result-item"
                    onClick={() => handleSearchResultClick(result)}
                  >
                    {result.type === 'chat-list' ? (
                      <div className="search-result-header">
                        <strong>Chat: {result.chatName}</strong>
                      </div>
                    ) : result.type === 'chat-message' ? (
                      <>
                        <div className="search-result-header">
                          <strong>Chat: {chats.find(c => c.id === result.chatId)?.name || 'Untitled Chat'}</strong>
                        </div>
                        <div className="search-result-content">
                          <p>
                            <strong>You: </strong> 
                            {highlightText(result.userMessage, result.highlightText)}
                          </p>
                          <p>
                            <strong>Bot: </strong> 
                            {highlightText(result.botMessage, result.highlightText)}
                          </p>
                        </div>
                      </>
                    ) : (
                      <div className="search-result-header">
                        <strong>File: {highlightText(result.filename, result.highlightText)}</strong>
                      </div>
                    )}
                  </div>
                ))
              ) : searchQuery ? (
                <div className="no-results">No results found</div>
              ) : (
                <div className="no-results">
                  {searchType === 'files' ? 'No uploaded files' : 'No created chats'}
                </div>
              )}
            </div>
            <div className="modal-buttons">
              <button
                className="cancel-button"
                onClick={() => setShowSearchModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {showEvaluationModal && (
        <div className="delete-confirm-modal">
          <div className="modal-content search-modal">
            {isEvaluating ? (
              <div className="loading-container">
                <div className="loading-spinner" />
                  {loadingMessages[loadingMessageIndex]}
              </div>
            ) : evaluationResult ? (
              <div className="result-container">
                <input
                  type="text"
                  style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Escape') {
                      setEvaluationResult(null); 
                      setGroundTruth("");
                      setShowEvaluationModal(false);
                    }
                  }}
                />
                <div className="header">
                  <h3>Evaluation Result</h3>
                  <div className="tooltip-container">
                    <span className="info-icon">?</span>
                    <div className="tooltip-text">
                      <strong>Metrics explained:</strong><br /><br />
                      <strong>Faithfulness</strong>:   Measures the factual accuracy of the generated answer based on the context.<br />
                       Computed using the <em>question</em>, <em>contexts</em>, and the <em>answer</em>.<br /><br />
                      <strong>Answer Relevancy</strong>: Measures how relevant the generated answer is to the question.<br />
                      Computed using the <em>question</em> and the <em>answer</em>.<br />
                      E.g., if only part of the question is answered, this score is low.<br /><br />
                      <strong>Context Precision</strong>: Measures the signal-to-noise ratio of the retrieved context.<br />
                      Computed using the <em>question</em> and the <em>contexts</em>.<br /><br />   
                      <strong>Context Recall</strong>: Measures if all relevant information required to answer the question was retrieved.<br />
                      Computed using the <em>ground truth</em> and the <em>contexts</em>.<br />
                      <strong>This is the only metric that uses human-annotated ground truth.</strong><br /><br />
                    </div>
                  </div>
                </div>
                <table className="result-table">
                  <tbody>
                    {evaluationKeys.map((key) => {
                      const value = evaluationResult[key];
                      let valueClass = "";
                      if (value >= 0.85) valueClass = "score-high";
                      else if (value >= 0.7) valueClass = "score-medium-high";
                      else if (value >= 0.5) valueClass = "score-medium";
                      else if (value >= 0.3) valueClass = "score-medium-low";
                      else valueClass = "score-low";

                      return (
                        <tr key={key}>
                          <td className="result-key">{key}</td>
                          <td className={`result-value ${valueClass}`}>
                            {value !== null && value !== undefined ? value : "N/A"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>

                <div className="modal-buttons">
                  <button
                    className="create-button"
                    onClick={() => {
                      setEvaluationResult(null); 
                      setGroundTruth("");
                    }}
                  >
                    Provide answer again
                  </button>
                  <button
                    className="cancel-button"
                    onClick={() => {
                      setEvaluationResult(null); 
                      setGroundTruth("");
                      setShowEvaluationModal(false);
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <>
                <h3>
                  Provide answer to this question
                </h3>
                <div className="search-input-container">
                  <textarea
                    ref={groundTruthInputRef}
                    value={groundTruth}
                    placeholder="Enter answer"
                    onChange={(e) => setGroundTruth(e.target.value)}
                    rows={5}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        evaluateAnswer(currentEvalIndex);
                      }
                      if (e.key === "Escape") {
                        setShowEvaluationModal(false);
                        setGroundTruth("");
                      }
                    }}
                    className="evaluate-textarea"
                  />
                </div>
                <div className="modal-buttons">
                  <button
                    className="create-button"
                    onClick={() => evaluateAnswer(currentEvalIndex)}
                  >
                    Evaluate
                  </button>
                  <button
                    className="cancel-button"
                    onClick={() => {
                      setShowEvaluationModal(false);
                      setGroundTruth("");
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
      <aside className="sidebar">
        <div className="section-header">
          <button className="action-button" onClick={handleCreateChat}>
            + New Chat
          </button>
          <button 
            className="action-button"
            onClick={() => openSearchModal('chats')}
            disabled={isLoading}
          >
            <div className="search-button">
              <div className="search">
                <Search size={15} />
              </div>
              <div>
                Search Chats
              </div> 
            </div>
          </button>
        </div>
        <h3>Chats</h3>
          {chats.length > 0 ? (
            <ul className="chat-history">
              {chats.map((chat, index) => (
                <li
                  key={chat.id}
                  className={selectedChat?.id === chat.id ? "active" : ""}
                  onClick={(e) => {
                    if (isLoading) return;
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
          ) : (
            <div className="no-content">
              No chats yet. Start a new conversation!
            </div>
          )}
      </aside>
      <main className="chat-center">
        {selectedChat ? (
          <div className="chat-window">
            <div className="chat-header">
              <h3>{selectedChat.name}</h3>
            </div>
           <div className="messages">
              {messages.length === 0 && (
                <div className="chat-intro-message">
                  How can I help you today?
                </div>
              )}
              {messages.map((msg, idx) => (
                <div key={idx}  className={`message-wrapper ${msg.sender} ${msg.isHighlighted ? 'highlighted' : ''}`}>
                  {msg.sender === 'user' && msg.isEditing ? (
                    <EditableTextArea
                      value={msg.text}
                      onChange={(e) => {
                        shouldScrollRef.current = false;
                        const updatedMessages = [...messages];
                        updatedMessages[idx].text = e.target.value;
                        setMessages(updatedMessages);
                      }}
                      onKeyDown={async (e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          shouldScrollRef.current = false;
                          await saveEditedMessage(idx);
                        }
                        if (e.key === 'Escape') {
                          shouldScrollRef.current = false;
                          const updatedMessages = [...messages];
                          updatedMessages[idx].isEditing = false;
                          updatedMessages[idx].text = originalMessage
                          setMessages(updatedMessages);
                        }
                      }}
                      autoFocus={true}
                    />
                  ) : (
                    <div className="message-parent">
                      <div>
                      {msg.sender === "bot" && msg.text !== "Typing..." && (
                        <img
                        className="bot-icon"
                        src="health-svgrepo-com.svg"
                        alt="Bot"
                        width={27}
                        height={27}
                      />
                      )}
                      </div>
                      <div>
                        <div className={`message ${msg.sender}`}>
                          {msg.text === "Typing..." ? (
                            <TypingIndicator />
                          ) : (
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {msg.text}
                            </ReactMarkdown>
                          )}
                        </div>
                        <div className="message-actions">
                          {msg.sender === 'user' && !msg.isEditing && (
                            <div className="action-wrapper">
                              <button
                                className="edit-message-button"
                                onClick={(e) => {
                                  shouldScrollRef.current = false;
                                  const updatedMessages = messages.map((msg, i) => ({
                                    ...msg,
                                    isEditing: i === idx,
                                  }));
                                  setOriginalMessage(msg.text);
                                  setMessages(updatedMessages);
                                }}
                                disabled={isLoading}
                              >
                                <Pencil size={18} color={isLoading ? "#ccc" : "#555"} />
                              </button>
                              <div className="tooltip-text">Edit</div>
                            </div>
                          )}

                          {msg.sender === 'user' && !msg.isEditing && (
                            <div className="action-wrapper">
                              <button
                                className="evaluate-message-button"
                                onClick={() =>
                                  openEvaluateModal(idx)
                                }
                                disabled={isLoading}
                              >
                                <FileCheck size={18} color={isLoading ? "#ccc" : "#555"} />
                              </button>
                              <div className="tooltip-text">Evaluate</div>
                            </div>
                          )}

                          {!msg.isEditing && (
                            <div className="action-wrapper">
                              <button
                                className="copy-message-button"
                                onClick={() => copyToClipboard(msg.text)}
                                disabled={isLoading && msg.sender === 'bot'}
                              >
                                <Copy size={18} color={isLoading && msg.sender === 'bot' ? "#ccc" : "#555"} />
                              </button>
                              <div className="tooltip-text">Copy</div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                  {msg.sender === 'user' && msg.isEditing && (
                    <div className="edit-actions">
                      <button
                        className="save-edit-button"
                        onClick={() => { 
                          saveEditedMessage(idx)
                        }}
                        disabled={isLoading}
                      >
                        Send
                      </button>
                      <button
                        className="cancel-edit-button"
                        onClick={() => {
                          shouldScrollRef.current = false;
                          const updatedMessages = [...messages];
                          updatedMessages[idx].isEditing = false;
                          updatedMessages[idx].text = originalMessage
                          setMessages(updatedMessages);
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </div>
              ))}
            <div ref={messagesEndRef} />
            </div>
            <div className="input-area">
             <CustomInputArea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onButtonClick={handleSend}
              placeholder="Type your message..."
              buttonLabel="Send"
              isLoading={isLoading}
              autoFocus={true}
            />
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
            accept=".pdf,application/pdf" 
          />
          <button 
            className="action-button"
            onClick={() => openSearchModal('files')}
          >
            <div className="search-button">
              <div className="search">
                <Search size={15} />
              </div>
              <div>
                Search Files
              </div> 
            </div>
          </button>
        </div>
        <h3>Files</h3>
        {uploadedFiles.length > 0 ? (
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
        ) : (
          <div className="no-content">
            No files yet. Upload a new file!
          </div>
        )}
      </aside>
    </div>
  );
}

export default MainPage;