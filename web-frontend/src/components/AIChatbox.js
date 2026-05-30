import React, { useState, useRef, useEffect } from 'react';
import { BsXLg, BsArrowRightCircleFill } from 'react-icons/bs';
import { useNavigate } from 'react-router-dom';
import jwtDecode from 'jwt-decode';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import axiosAuthInstance from '../utils/axios-auth-instance';

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
  const navigate = useNavigate();

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
      const aiBaseUrl = process.env.REACT_APP_BACKEND_URL.includes('localhost') 
        ? 'http://localhost:8000' 
        : process.env.REACT_APP_BACKEND_URL.replace(/\/$/, "") + '/ai/';
      //const aiBaseUrl = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "") + '/ai/';
      const response = await fetch(`${aiBaseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          query: userText,
          history: messages.filter((msg, index) => !(index === 0 && msg.text === 'Halo! Ada yang bisa saya bantu?'))
        }),
      });

      if (!response.ok) {
        throw new Error('Jaringan bermasalah atau API error');
      }

      const data = await response.json();
      const aiReply = data.reply;
      
      if (data.command) {
        const { type, target } = data.command;

        if (target === 'automate_shipment') {
          try {
            setMessages((prev) => [
              ...prev,
              { sender: 'ai', text: 'Memproses optimisasi rute di background, mohon tunggu beberapa saat...' },
            ]);
            
            const { start_date, end_date, optimization_type, customer_id, kabupaten_kota, so_origin, delivery_order_num } = data.command.data || {};
            let optType = optimization_type || 'distance';
            if (optType === 'route') {
              optType = 'distance';
            } else if (optType === 'volume') {
              optType = 'load';
            } else if (optType === 'distance_volume') {
              optType = 'balance';
            }
            
            let url = `/delivery-orders?skip=0&limit=1000&status=READY`;
            if (start_date && end_date) {
              const formattedStartDate = new Date(start_date).toLocaleDateString('id-ID', { day: '2-digit', month: '2-digit', year: 'numeric' });
              const formattedEndDate = new Date(end_date).toLocaleDateString('id-ID', { day: '2-digit', month: '2-digit', year: 'numeric' });
              url += `&start_date=${formattedStartDate}&end_date=${formattedEndDate}`;
            }
            if (customer_id) {
              url += `&customer_id=${customer_id}`;
            }
            if (kabupaten_kota) {
              url += `&kabupaten_kota=${encodeURIComponent(kabupaten_kota)}`;
            }
            if (so_origin) {
              url += `&so_origin=${encodeURIComponent(so_origin)}`;
            }
            if (delivery_order_num) {
              url += `&delivery_order_num=${encodeURIComponent(delivery_order_num)}`;
            }
            
            const doResponse = await axiosAuthInstance.get(url);
            const deliveryOrders = doResponse.data?.data?.deliveryOrders || [];
            
            if (deliveryOrders.length === 0) {
              const errMsg = 'Maaf, tidak ada Delivery Order yang berstatus READY pada kriteria filter tersebut untuk DC Anda.';
              setMessages((prev) => [
                ...prev,
                { sender: 'ai', text: errMsg },
              ]);
              alert(errMsg); // Add alert so user clearly sees why it didn't navigate
              setIsLoading(false);
              return;
            }
            
            const doIds = deliveryOrders.map(item => item.id);
            
            let dc_id = '';
            const token = sessionStorage.getItem('token');
            if (token) {
              const decodedToken = jwtDecode(token);
              dc_id = decodedToken.dc_id || decodedToken.role?.dc_id; // Check both places
            }
            
            const optResponse = await axiosAuthInstance.post(
              `priority-opt?preview=true`,
              { delivery_orders_id: doIds, priority: optType },
              { headers: { dc_id: dc_id }, timeout: 600000 }
            );
            
            console.log('Pengiriman otomatis berhasil:', optResponse.data);
            const shipmentsResult = optResponse.data?.data?.shipments || [];
            
            if (shipmentsResult.length === 0) {
              const errMsg = 'Maaf, algoritma tidak dapat membentuk pengiriman (mungkin karena kapasitas truk tidak mencukupi, tidak ada truk tersedia, atau lokasi tidak terjangkau).';
              setMessages((prev) => [
                ...prev,
                { sender: 'ai', text: errMsg },
              ]);
              alert(errMsg);
              setIsLoading(false);
              return;
            }
            
            setMessages((prev) => [
              ...prev,
              { sender: 'ai', text: 'Pratinjau pengiriman berhasil dibuat! Mengalihkan ke halaman tinjauan pengiriman...' },
            ]);
            
            setTimeout(() => {
              let userRole = '';
              if (token) {
                const decodedToken = jwtDecode(token);
                userRole = decodedToken.role?.name;
              }
              const basePath = userRole === 'Super' ? '/administrator' : '';
              // Store response data to pass it to the review page
              sessionStorage.setItem('automate_shipment_data', JSON.stringify(optResponse.data));
              navigate(`${basePath}/pengiriman/otomatisasi`, { state: { optResponse: optResponse.data } });
            }, 2500);
            
          } catch (error) {
            console.error('Gagal membuat pengiriman otomatis:', error);
            const errMsg = 'Terjadi kesalahan saat memproses optimisasi rute atau server terlalu sibuk.';
            setMessages((prev) => [
              ...prev,
              { sender: 'ai', text: errMsg },
            ]);
            alert(errMsg);
          } finally {
            setIsLoading(false);
          }
          return;
        }

        const routeMap = {
          'shipments_list': '/pengiriman',
          'add_shipment': '/shipment/tambah',
          'edit_shipment': '/shipment/edit',
          'trucks_list': '/truk',
          'add_truck': '/truk/buat',
          'bulk_add_truck': '/truk/bulk-buat',
          'edit_truck': '/truk/update',
          'bulk_edit_truck': '/truk/bulk-ubah',
          'delivery_orders_list': '/delivery-order',
          'add_delivery_order': '/delivery-order/tambah',
          'edit_delivery_order': '/delivery-order/edit',
          'locations_list': '/lokasi',
          'add_location': '/lokasi/buat',
          'edit_location': '/lokasi/update',
          'dashboard': '/dashboard',
          'products_line_list': '/product-line',
          'add_product_line': '/product-line/tambah',
          'edit_product_line': '/product-line/edit',
          'products_list': '/product',
          'add_product': '/product/tambah',
          'edit_product': '/product/edit',
          'customers_list': '/customer',
          'add_customer': '/customer/tambah',
          'edit_customer': '/customer/edit',
          'users_list': '/user',
          'add_user': '/user/tambah',
          'edit_user': '/user/edit',
          'roles_list': '/role',
          'add_role': '/role/tambah',
          'edit_role': '/role/edit',
        };

        if (routeMap[target]) {
          try {
            const token = sessionStorage.getItem('token');
            let userRole = '';
            if (token) {
              const decodedToken = jwtDecode(token);
              userRole = decodedToken.role?.name;
            }
            const basePath = userRole === 'Super' ? '/administrator' : '';
            navigate(`${basePath}${routeMap[target]}`, { state: data.command.data });
          } catch (error) {
            console.error('Error saat decode token untuk navigasi', error);
          }
        }
      }

      setMessages((prev) => [
        ...prev,
        { sender: 'ai', text: aiReply },
      ]);
    } catch (error) {
      console.error('Error fetching AI response:', error);
      setMessages((prev) => [
        ...prev,
        { sender: 'ai', text: 'Maaf, gagal terhubung ke agen AI atau terjadi kesalahan server.' },
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
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({node, ...props}) => <p className="mb-0" {...props} />,
                  ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-2" {...props} />,
                  ol: ({node, ...props}) => <ol className="list-decimal ml-4 mb-2" {...props} />,
                  li: ({node, ...props}) => <li className="mb-1" {...props} />,
                  table: ({node, ...props}) => (
                    <div className="overflow-x-auto my-2">
                      <table className="min-w-full border-collapse border border-gray-400 text-[11px]" {...props} />
                    </div>
                  ),
                  th: ({node, ...props}) => <th className="border border-gray-400 px-2 py-1 bg-gray-200" {...props} />,
                  td: ({node, ...props}) => <td className="border border-gray-400 px-2 py-1" {...props} />,
                }}
              >
                {msg.text}
              </ReactMarkdown>
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
