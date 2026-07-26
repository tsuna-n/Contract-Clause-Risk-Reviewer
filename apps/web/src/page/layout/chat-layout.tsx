import { useState } from "react";
import Sidebar, { type Infro } from "../../component/sidebar/sidebar";
import FileUploadPage from "../chat";
import Detail from "../detail";

function Chat() {
  const [selectedChat, setSelectedChat] = useState<Infro | null>(null);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Sidebar */}
      <div className="flex-1 rounded-lg p-4 overflow-hidden">
        <Sidebar
          onNewChat={() => setSelectedChat(null)}
          onSelectChat={(infro) => setSelectedChat(infro)}
        />
      </div>

      {/* Main Content */}
      <div className="flex-[3] m-3 rounded-lg flex flex-col h-[calc(100vh-1.5rem)]">
        <div className="flex-1 min-h-0 border-2 border-gray-400 rounded-lg my-1 overflow-y-auto">
          {selectedChat ? (
            <Detail infro={selectedChat} onBack={() => setSelectedChat(null)} />
          ) : (
            <FileUploadPage />
          )}
        </div>
      </div>
    </div>
  );
}

export default Chat;