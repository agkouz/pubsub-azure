import React, { useState, useEffect, useRef } from "react";
import "./App.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000/ws";

console.log(BACKEND_URL);
console.log(WS_URL);

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState("");
  const [connectionStatus, setConnectionStatus] = useState("Disconnected");
  const [currentRoom, setCurrentRoom] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [joinedRooms, setJoinedRooms] = useState(new Set());
  const [username, setUsername] = useState(
    "User" + Math.floor(Math.random() * 1000)
  );

  // Room creation modal
  const [showCreateRoom, setShowCreateRoom] = useState(false);
  const [newRoomName, setNewRoomName] = useState("");
  const [newRoomDescription, setNewRoomDescription] = useState("");

  const ws = useRef(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadRooms();
    connectWebSocket();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadRooms = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/rooms`);
      const data = await response.json();
      setRooms(data);

      // Auto-select first room if none selected
      if (data.length > 0 && !currentRoom) {
        const firstRoom = data[0];
        setCurrentRoom(firstRoom);
      }
    } catch (error) {
      console.error("Failed to load rooms:", error);
      addSystemMessage("Failed to load rooms", "error");
    }
  };

  const connectWebSocket = () => {
    ws.current = new WebSocket(`${WS_URL}?user_id=${username}`);

    ws.current.onopen = () => {
      console.log("WebSocket connected");
      setConnectionStatus("Connected");
      addSystemMessage(`Connected as ${username}`);
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "room_joined") {
          addSystemMessage(`✓ Joined: ${data.room.name}`);
          setJoinedRooms((prev) => new Set([...prev, data.room.id]));
        } else if (data.type === "room_left") {
          addSystemMessage(`✓ Left room`);
          setJoinedRooms((prev) => {
            const newSet = new Set(prev);
            newSet.delete(data.room_id);
            return newSet;
          });
        } else if (data.type === "rooms_updated") {
          // Room list changed, reload
          setRooms(data.rooms);
          addSystemMessage("Room list updated");
        } else if (data.type === "rooms_list") {
          setRooms(data.rooms);
        } else if (data.type === "error") {
          addSystemMessage(`Error: ${data.message}`, "error");
        } else if (data.content) {
          // Regular message
          addMessage(data.content, data.sender, data.room_id, data.room_name);
        } else if (
          data.type === "message_publish" &&
          data.status === "success"
        ) {
          // Optional: confirm message delivered
          console.log("Server acknowledged message.");
        }
      } catch (error) {
        console.error("Error parsing message:", error);
      }
    };

    ws.current.onclose = () => {
      console.log("WebSocket disconnected");
      setConnectionStatus("Disconnected");
      addSystemMessage("Disconnected", "error");
      setJoinedRooms(new Set());

      setTimeout(() => {
        if (ws.current?.readyState === WebSocket.CLOSED) {
          console.log("Reconnecting...");
          connectWebSocket();
        }
      }, 3000);
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error:", error);
      setConnectionStatus("Error");
    };
  };

  const joinRoom = (roomId) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          action: "join",
          room_id: roomId,
        })
      );
    }
  };

  const leaveRoom = (roomId) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(
        JSON.stringify({
          action: "leave",
          room_id: roomId,
        })
      );
    }
  };

  const createRoom = async () => {
    if (!newRoomName.trim()) {
      alert("Room name is required");
      return;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/rooms`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: newRoomName,
          description: newRoomDescription,
          created_by: username,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to create room");
      }

      const newRoom = await response.json();
      addSystemMessage(`✓ Created room: ${newRoom.name}`);

      // Close modal and reset
      setShowCreateRoom(false);
      setNewRoomName("");
      setNewRoomDescription("");

      // Reload rooms
      await loadRooms();

      // Auto-join the new room
      setCurrentRoom(newRoom);
      joinRoom(newRoom.id);
    } catch (error) {
      console.error("Failed to create room:", error);
      alert(error.message);
    }
  };

  const deleteRoom = async (roomId) => {
    if (!window.confirm("Are you sure you want to delete this room?")) {
      return;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/rooms/${roomId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        throw new Error("Failed to delete room");
      }

      addSystemMessage("Room deleted");
      await loadRooms();

      if (currentRoom?.id === roomId) {
        setCurrentRoom(rooms[0] || null);
      }
    } catch (error) {
      console.error("Failed to delete room:", error);
      alert("Failed to delete room");
    }
  };

  const addMessage = (content, sender, roomId, roomName) => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages((prev) => [
      ...prev,
      {
        content,
        sender,
        timestamp,
        roomId,
        roomName,
        type: "message",
      },
    ]);
  };

  const addSystemMessage = (content, type = "system") => {
    const timestamp = new Date().toLocaleTimeString();
    setMessages((prev) => [
      ...prev,
      {
        content,
        timestamp,
        type,
      },
    ]);
  };

  const sendMessage = () => {
    if (!inputMessage.trim() || !currentRoom || !ws.current) return;
    if (ws.current.readyState !== WebSocket.OPEN) {
      addSystemMessage(
        "WebSocket is not connected. Message not sent.",
        "error"
      );
      return;
    }

    try {
      ws.current.send(
        JSON.stringify({
          action: "message_publish",
          data: {
            room_id: currentRoom.id,
            content: inputMessage,
            sender: username,
          },
        })
      );

      setInputMessage("");
    } catch (error) {
      console.error("WebSocket send error:", error);
      addSystemMessage(`Failed to send: ${error.message}`, "error");
    }
  };

  const selectRoom = (room) => {
    setCurrentRoom(room);
    if (!joinedRooms.has(room.id)) {
      joinRoom(room.id);
    }
  };

  // Filter messages for current room
  const filteredMessages = currentRoom
    ? messages.filter(
        (msg) => msg.type !== "message" || msg.roomId === currentRoom.id
      )
    : messages.filter((msg) => msg.type !== "message");

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>💬 Dynamic Chatrooms</h1>
          {/* <input
            id="user-id"
            type="text"
            // disabled={isConnected}
            className="username-badge"
            placeholder="enter user ID..."
            onChange={(e) => setUsername(e.target.value)}
          /> */}
          {/*!username && (
            <button onClick={createRoom} className="btn-primary">
              Connect
            </button>
          )*/}
          {username && <span className="username-badge">@{username}</span>}
        </div>
        <div className={`connection-status ${connectionStatus.toLowerCase()}`}>
          {connectionStatus}
        </div>
      </header>

      <div className="main-content">
        {/* Sidebar */}
        <div className="sidebar">
          <div className="rooms-header">
            <h3>Rooms ({rooms.length})</h3>
            <button
              onClick={() => setShowCreateRoom(true)}
              className="btn-create"
              title="Create new room"
            >
              ➕
            </button>
          </div>

          <div className="rooms-list">
            {rooms.map((room) => (
              <div
                key={room.id}
                className={`room-item ${
                  currentRoom?.id === room.id ? "active" : ""
                } ${joinedRooms.has(room.id) ? "joined" : ""}`}
              >
                <div onClick={() => selectRoom(room)} className="room-info">
                  <div className="room-name-row">
                    <span className="room-name">#{room.name}</span>
                    {room.member_count > 0 && (
                      <span className="member-count">{room.member_count}</span>
                    )}
                  </div>
                  {room.description && (
                    <span className="room-description">{room.description}</span>
                  )}
                  <span className="room-meta">by {room.created_by}</span>
                </div>
                <div className="room-actions">
                  {joinedRooms.has(room.id) ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        leaveRoom(room.id);
                      }}
                      className="btn-toggle joined"
                      title="Leave room"
                    >
                      ✓
                    </button>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        joinRoom(room.id);
                      }}
                      className="btn-toggle"
                      title="Join room"
                    >
                      +
                    </button>
                  )}
                  {room.created_by === username && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteRoom(room.id);
                      }}
                      className="btn-delete"
                      title="Delete room"
                    >
                      🗑️
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <div className="chat-area">
          {currentRoom ? (
            <>
              <div className="room-header">
                <div>
                  <h2>#{currentRoom.name}</h2>
                  {currentRoom.description && (
                    <p className="room-description">
                      {currentRoom.description}
                    </p>
                  )}
                </div>
                {!joinedRooms.has(currentRoom.id) && (
                  <div className="warning">
                    ⚠️ You are not subscribed to this room
                  </div>
                )}
              </div>

              <div className="messages-container">
                {filteredMessages.map((msg, index) => (
                  <div
                    key={index}
                    className={`message ${msg.type || "message"} ${
                      msg.sender === username ? "own-message" : ""
                    }`}
                  >
                    {msg.type === "system" || msg.type === "error" ? (
                      <div className="system-message">
                        <span className="timestamp">[{msg.timestamp}]</span>{" "}
                        {msg.content}
                      </div>
                    ) : (
                      <>
                        <div className="message-header">
                          <span className="sender">{msg.sender}</span>
                          <span className="timestamp">{msg.timestamp}</span>
                        </div>
                        <div className="message-content">{msg.content}</div>
                      </>
                    )}
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              <div className="input-container">
                <input
                  type="text"
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={(e) => e.key === "Enter" && sendMessage()}
                  placeholder={`Message #${currentRoom.name}...`}
                  disabled={!joinedRooms.has(currentRoom.id)}
                />
                <button
                  onClick={sendMessage}
                  disabled={!joinedRooms.has(currentRoom.id)}
                >
                  Send
                </button>
              </div>
            </>
          ) : (
            <div className="no-room-selected">
              <h2>👋 Welcome!</h2>
              <p>Select or create a room to start chatting</p>
              <button
                onClick={() => setShowCreateRoom(true)}
                className="btn-create-large"
              >
                ➕ Create Your First Room
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Create Room Modal */}
      {showCreateRoom && (
        <div className="modal-overlay" onClick={() => setShowCreateRoom(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Room</h2>
            <div className="form-group">
              <label>Room Name *</label>
              <input
                type="text"
                value={newRoomName}
                onChange={(e) => setNewRoomName(e.target.value)}
                placeholder="e.g., Product Team"
                maxLength={50}
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea
                value={newRoomDescription}
                onChange={(e) => setNewRoomDescription(e.target.value)}
                placeholder="What's this room about?"
                maxLength={200}
                rows={3}
              />
            </div>
            <div className="modal-actions">
              <button
                onClick={() => setShowCreateRoom(false)}
                className="btn-cancel"
              >
                Cancel
              </button>
              <button onClick={createRoom} className="btn-primary">
                Create Room
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
