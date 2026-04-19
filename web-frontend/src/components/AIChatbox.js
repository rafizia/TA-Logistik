import React, { useState, useRef, useEffect } from 'react';
import { BsXLg, BsArrowRightCircleFill } from 'react-icons/bs';

export default function AIChatbox({ onClose }) {
  const [messages, setMessages] = useState([
    {
      sender: 'ai',
      text: 'Halo! Ada yang bisa saya bantu?',
    },
  ]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '40px';
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 120)}px`;
    }
  }, [inputText]);

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;

    const userText = inputText;

    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setInputText('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: userText }),
      });

      if (!response.ok) {
        throw new Error('Jaringan bermasalah atau API error');
      }

      const data = await response.json();
      
      const aiResponseText = data.response || data.reply || data.answer || data.message || (typeof data === 'string' ? data : JSON.stringify(data));

      setMessages((prev) => [
        ...prev,
        { sender: 'ai', text: aiResponseText },
      ]);
    } catch (error) {
      console.error('Error fetching AI response:', error);
      setMessages((prev) => [
        ...prev,
        { sender: 'ai', text: 'Maaf, gagal terhubung ke backend AI atau terjadi kesalahan server.' },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-full w-[280px] flex-shrink-0 bg-[#E8EAEF] shadow-[-4px_0_15px_rgba(0,0,0,0.05)] border-l border-neutral-30 flex flex-col z-[60] font-sans transition-all duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-6 pb-4 border-b border-white/50">
        <h3 className="font-bold text-[#1F54A3]">AI Assistant</h3>
        <button
          onClick={onClose}
          className="text-neutral-50 hover:text-neutral-80 transition-colors"
        >
          <BsXLg size={16} className="stroke-[0.5px]" />
        </button>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 pt-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex flex-col ${
              msg.sender === 'user' ? 'items-end' : 'items-start'
            }`}
          >
            <div
              className={`p-3 max-w-[95%] text-[13px] leading-relaxed shadow-sm ${
                msg.sender === 'user'
                  ? 'bg-[#225CA9] text-white rounded-[14px] rounded-tr-[4px]'
                  : 'bg-[#D1D3D4] text-[#333] rounded-[14px] rounded-tl-[4px]'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        
        {/* Loading Indicator */}
        {isLoading && (
          <div className="flex flex-col items-start">
            <div className="p-3 max-w-[95%] text-[13px] leading-relaxed shadow-sm bg-[#D1D3D4] text-[#333] rounded-[14px] rounded-tl-[4px] animate-pulse">
              Berpikir...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 pt-2">
        <div className="relative bg-[#D3D2D3] rounded-[20px] flex items-end pr-1 pb-1 border border-white/40 min-h-[40px]">
          <textarea
            ref={textareaRef}
            rows={1}
            className="w-full bg-transparent text-[13px] text-neutral-80 px-3 py-2.5 outline-none resize-none placeholder:text-neutral-50 overflow-y-auto flex items-center"
            placeholder="Tanyakan apapun..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
          ></textarea>
          <button
            onClick={handleSend}
            className={`rounded-full p-[6px] transition-colors ${
              inputText.trim()
                ? 'text-[#225CA9] hover:text-[#184481]'
                : 'text-neutral-50 cursor-not-allowed'
            }`}
            disabled={!inputText.trim()}
          >
            <BsArrowRightCircleFill size={24} />
          </button>
        </div>
      </div>
    </div>
  );
}
