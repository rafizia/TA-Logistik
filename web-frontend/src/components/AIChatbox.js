import { useState, useRef, useEffect } from 'react';
import {
  BsXLg,
  BsArrowRightCircleFill,
  BsPlusLg,
  BsTrash,
  BsClockHistory,
} from 'react-icons/bs';
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
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState('');
  const [showSessionsPanel, setShowSessionsPanel] = useState(false);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);

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

  // Load chat sessions & initial history
  useEffect(() => {
    const initChat = async () => {
      const token = sessionStorage.getItem('token');
      let userId = 'default_user';
      if (token) {
        try {
          const decoded = jwtDecode(token);
          userId = decoded.id || decoded.sub || decoded.user_id || 'user';
        } catch (e) { }
      }

      let currentSessionId = sessionStorage.getItem('session_id');
      if (!currentSessionId) {
        currentSessionId = `user_${userId}_${Date.now()}`;
        sessionStorage.setItem('session_id', currentSessionId);
      }
      setActiveSessionId(currentSessionId);

      // Load sessions list & history
      await fetchSessions();
      await fetchHistory(currentSessionId);
    };

    initChat();
  }, []);

  const fetchSessions = async () => {
    setIsLoadingSessions(true);
    try {
      const response = await axiosAuthInstance.get('/chat-sessions?limit=20&skip=0');
      if (response.data && response.data.data) {
        setSessions(response.data.data.sessions || []);
      }
    } catch (error) {
      console.error('Gagal mengambil daftar sesi chat:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  const fetchHistory = async (sessionId) => {
    if (!sessionId) return;
    setIsLoadingHistory(true);
    try {
      const response = await axiosAuthInstance.get(`/chat-history?session_id=${sessionId}`);
      if (response.data && response.data.data && Array.isArray(response.data.data)) {
        const fetchedMessages = response.data.data;
        if (fetchedMessages.length > 0) {
          setMessages(
            fetchedMessages.map((m) => ({
              sender: m.sender,
              text: m.text,
            }))
          );
        } else {
          setMessages([
            {
              sender: 'ai',
              text: 'Halo! Ada yang bisa saya bantu?',
            },
          ]);
        }
      }
    } catch (error) {
      console.error('Gagal mengambil histori chat:', error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleSelectSession = async (session) => {
    const selectedId = session.session_id;
    setActiveSessionId(selectedId);
    sessionStorage.setItem('session_id', selectedId);
    await fetchHistory(selectedId);
  };

  const handleNewChat = () => {
    const token = sessionStorage.getItem('token');
    let userId = 'user';
    if (token) {
      try {
        const decoded = jwtDecode(token);
        userId = decoded.id || decoded.sub || decoded.user_id || 'user';
      } catch (e) { }
    }

    const newSessionId = `user_${userId}_${Date.now()}`;
    sessionStorage.setItem('session_id', newSessionId);
    setActiveSessionId(newSessionId);

    setMessages([
      {
        sender: 'ai',
        text: 'Halo! Ada yang bisa saya bantu?',
      },
    ]);
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      await axiosAuthInstance.delete(`/chat-sessions/${sessionId}`);
      await fetchSessions();

      if (sessionId === activeSessionId) {
        handleNewChat();
      }
    } catch (error) {
      console.error('Gagal menghapus sesi:', error);
    }
  };

  const saveMessagesToDb = async (sessionId, userText, aiReplyText) => {
    try {
      await axiosAuthInstance.post('/chat-messages', {
        session_id: sessionId,
        messages: [
          { sender: 'user', text: userText },
          { sender: 'ai', text: aiReplyText },
        ],
      });
      // Refresh session list to update titles/previews
      fetchSessions();
    } catch (error) {
      console.error('Gagal menyimpan pesan ke database:', error);
    }
  };

  const handleSend = async () => {
    if (!inputText.trim() || isLoading) return;

    const userText = inputText;

    setMessages((prev) => [...prev, { sender: 'user', text: userText }]);
    setInputText('');
    setIsLoading(true);

    try {
      const aiBaseUrl = process.env.REACT_APP_BACKEND_URL?.includes('localhost')
        ? 'http://localhost:8000'
        : (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '') + '/ai/';

      let userDcId = null;
      let userDcName = null;
      let userRoleName = null;
      const tokenForAI = sessionStorage.getItem('token');
      if (tokenForAI) {
        try {
          const decoded = jwtDecode(tokenForAI);
          userRoleName = decoded.role?.name;
          userDcId = decoded.role?.dc_id || decoded.dc_id;
          if (userDcId) {
            userDcName = decoded.role?.dc_name || null;
          }
        } catch (e) { }
      }

      let sessionId = activeSessionId || sessionStorage.getItem('session_id') || 'default_session';

      const response = await fetch(`${aiBaseUrl}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: userText,
          session_id: sessionId,
          history: messages.filter(
            (msg, index) => !(index === 0 && msg.text === 'Halo! Ada yang bisa saya bantu?')
          ),
          user_context: {
            role: userRoleName,
            dc_id: userDcId,
            dc_name: userDcName,
            token: tokenForAI,
          },
        }),
      });

      if (!response.ok) {
        throw new Error('Jaringan bermasalah atau API error');
      }

      const data = await response.json();
      const aiReply = data.reply || 'Respons tidak tersedia.';

      if (data.command) {
        const { target } = data.command;

        if (target === 'automate_shipment') {
          try {
            setMessages((prev) => [
              ...prev,
              {
                sender: 'ai',
                text: 'Memproses optimisasi rute di background, mohon tunggu beberapa saat...',
              },
            ]);

            const {
              start_date,
              end_date,
              optimization_type,
              customer_id,
              kabupaten_kota,
              so_origin,
              delivery_order_num,
              delivery_order_ids,
            } = data.command.data || {};
            let optType = optimization_type || 'distance';
            if (optType === 'route') {
              optType = 'distance';
            } else if (optType === 'volume') {
              optType = 'load';
            } else if (optType === 'distance_volume') {
              optType = 'balance';
            }

            let doIds;

            if (
              delivery_order_ids &&
              Array.isArray(delivery_order_ids) &&
              delivery_order_ids.length > 0
            ) {
              doIds = delivery_order_ids;
            } else {
              let url = `/delivery-orders?skip=0&limit=1000&status=READY`;
              if (start_date && end_date) {
                const formattedStartDate = new Date(start_date).toLocaleDateString('id-ID', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                });
                const formattedEndDate = new Date(end_date).toLocaleDateString('id-ID', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                });
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
                const errMsg =
                  'Maaf, tidak ada Delivery Order yang berstatus READY pada kriteria filter tersebut untuk DC Anda.';
                setMessages((prev) => [...prev, { sender: 'ai', text: errMsg }]);
                await saveMessagesToDb(sessionId, userText, errMsg);
                alert(errMsg);
                setIsLoading(false);
                return;
              }

              doIds = deliveryOrders.map((item) => item.id);
            }

            let dc_id = '';
            const token = sessionStorage.getItem('token');
            if (token) {
              const decodedToken = jwtDecode(token);
              dc_id = decodedToken.dc_id || decodedToken.role?.dc_id;
            }

            const optResponse = await axiosAuthInstance.post(
              `priority-opt?preview=true`,
              { delivery_orders_id: doIds, priority: optType },
              { headers: { dc_id: dc_id }, timeout: 600000 }
            );

            const shipmentsResult = optResponse.data?.data?.shipments || [];

            if (shipmentsResult.length === 0) {
              const errMsg =
                'Maaf, algoritma tidak dapat membentuk pengiriman (mungkin karena kapasitas truk tidak mencukupi, tidak ada truk tersedia, atau lokasi tidak terjangkau).';
              setMessages((prev) => [...prev, { sender: 'ai', text: errMsg }]);
              await saveMessagesToDb(sessionId, userText, errMsg);
              alert(errMsg);
              setIsLoading(false);
              return;
            }

            const successMsg =
              'Pratinjau pengiriman berhasil dibuat! Mengalihkan ke halaman tinjauan pengiriman...';
            setMessages((prev) => [...prev, { sender: 'ai', text: successMsg }]);
            await saveMessagesToDb(sessionId, userText, successMsg);

            setTimeout(() => {
              let userRole = '';
              if (token) {
                const decodedToken = jwtDecode(token);
                userRole = decodedToken.role?.name;
              }
              const basePath = userRole === 'Super' ? '/administrator' : '';
              sessionStorage.setItem('automate_shipment_data', JSON.stringify(optResponse.data));
              navigate(`${basePath}/pengiriman/otomatisasi`, {
                state: { optResponse: optResponse.data },
              });
            }, 2500);
          } catch (error) {
            console.error('Gagal membuat pengiriman otomatis:', error);
            const errMsg =
              'Terjadi kesalahan saat memproses optimisasi rute atau server terlalu sibuk.';
            setMessages((prev) => [...prev, { sender: 'ai', text: errMsg }]);
            await saveMessagesToDb(sessionId, userText, errMsg);
            alert(errMsg);
          } finally {
            setIsLoading(false);
          }
          return;
        }

        const routeMap = {
          shipments_list: '/pengiriman',
          add_shipment: '/shipment/tambah',
          edit_shipment: '/shipment/edit',
          trucks_list: '/truk',
          add_truck: '/truk/buat',
          bulk_add_truck: '/truk/bulk-buat',
          edit_truck: '/truk/update',
          bulk_edit_truck: '/truk/bulk-ubah',
          delivery_orders_list: '/delivery-order',
          add_delivery_order: '/delivery-orders/create',
          edit_delivery_order: '/delivery-orders/edit',
          locations_list: '/lokasi',
          add_location: '/lokasi/buat',
          edit_location: '/lokasi/update',
          dashboard: '/dashboard',
          products_line_list: '/product-line',
          add_product_line: '/product-line/tambah',
          edit_product_line: '/product-line/edit',
          products_list: '/product',
          add_product: '/product/tambah',
          edit_product: '/product/edit',
          customers_list: '/customer',
          add_customer: '/customer/tambah',
          edit_customer: '/customer/edit',
          users_list: '/user',
          add_user: '/user/tambah',
          edit_user: '/user/edit',
          roles_list: '/role',
          add_role: '/role/tambah',
          edit_role: '/role/edit',
          detail_location: '/lokasi',
          detail_customer: '/customer',
          detail_delivery_order: '/delivery-order',
          detail_shipment: '/pengiriman',
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
            let finalRoute = `${basePath}${routeMap[target]}`;

            let payload = data.command.data;
            if (payload) {
              if (payload.id !== undefined && payload.Id === undefined) {
                payload.Id = payload.id;
              } else if (payload.Id !== undefined && payload.id === undefined) {
                payload.id = payload.Id;
              }
            }

            if (
              (target === 'detail_location' ||
                target === 'detail_customer' ||
                target === 'detail_delivery_order' ||
                target === 'edit_delivery_order' ||
                target === 'detail_shipment') &&
              payload &&
              payload.id
            ) {
              finalRoute = `${finalRoute}/${payload.id}`;
            }

            navigate(finalRoute, { state: payload });
          } catch (error) {
            console.error('Error saat decode token untuk navigasi', error);
          }
        }
      }

      setMessages((prev) => [...prev, { sender: 'ai', text: aiReply }]);

      // Persist messages to DB
      await saveMessagesToDb(sessionId, userText, aiReply);
    } catch (error) {
      console.error('Error fetching AI response:', error);
      const errMsg = 'Maaf, gagal terhubung ke agen AI atau terjadi kesalahan server.';
      setMessages((prev) => [...prev, { sender: 'ai', text: errMsg }]);
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
    <div
      className={`h-full ${showSessionsPanel ? 'w-[400px]' : 'w-[300px]'
        } flex-shrink-0 bg-[#E8EAEF] shadow-[-4px_0_15px_rgba(0,0,0,0.05)] border-l border-neutral-30 flex z-[60] font-sans transition-all duration-300`}
    >
      {/* Side Sessions Panel */}
      {showSessionsPanel && (
        <div className="w-[140px] bg-[#D8DCE5] border-r border-gray-300 flex flex-col h-full">
          <div className="px-3 pt-4 pb-3 border-b border-gray-300 flex items-center justify-between">
            <span className="text-[16px] font-bold text-[#1F54A3]">Histori</span>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {isLoadingSessions ? (
              <div className="text-[11px] text-gray-500 text-center py-4">Memuat...</div>
            ) : sessions.length === 0 ? (
              <div className="text-[11px] text-gray-500 text-center py-4">Belum ada sesi</div>
            ) : (
              sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => handleSelectSession(s)}
                  className={`group flex items-center justify-between p-2 rounded cursor-pointer text-[11px] transition-colors ${s.session_id === activeSessionId
                    ? 'bg-[#1F54A3] text-white font-semibold'
                    : 'bg-white/60 text-gray-700 hover:bg-white'
                    }`}
                >
                  <div className="truncate flex-1 pr-1" title={s.title || 'Sesi Chat'}>
                    {s.title || 'Sesi Chat'}
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(e, s.session_id)}
                    className={`opacity-0 group-hover:opacity-100 ${s.session_id === activeSessionId ? 'text-white' : 'text-red-500'} hover:text-red-700 transition-opacity`}
                    title="Hapus Sesi"
                  >
                    <BsTrash size={11} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Main Chat Panel */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 pt-4 pb-3 border-b border-white/50 bg-[#E8EAEF]">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setShowSessionsPanel(!showSessionsPanel)}
              className="p-1.5 rounded-md text-[#1F54A3] hover:bg-white/50 transition-colors flex items-center space-x-1"
              title={showSessionsPanel ? 'Sembunyikan Sesi' : 'Lihat Histori Sesi'}
            >
              <BsClockHistory size={16} />
            </button>
            <h3 className="font-bold text-[#1F54A3] text-[16px]">AI Assistant</h3>
          </div>

          <div className="flex items-center space-x-1">
            <button
              onClick={handleNewChat}
              className="p-1.5 text-[#1F54A3] hover:bg-white/50 rounded-md transition-colors"
              title="Chat Baru"
            >
              <BsPlusLg size={16} />
            </button>
            <button
              onClick={onClose}
              className="text-neutral-50 hover:text-neutral-80 transition-colors p-1"
            >
              <BsXLg size={16} className="stroke-[0.5px]" />
            </button>
          </div>
        </div>

        {/* Message List */}
        <div className="flex-1 overflow-y-auto px-4 pb-4 pt-4 space-y-4">
          {isLoadingHistory ? (
            <div className="flex justify-center items-center h-20 text-[12px] text-gray-500">
              Memuat histori chat...
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'
                  }`}
              >
                <div
                  className={`p-3 max-w-[95%] text-[13px] leading-relaxed shadow-sm ${msg.sender === 'user'
                    ? 'bg-[#225CA9] text-white rounded-[14px] rounded-tr-[4px]'
                    : 'bg-[#D1D3D4] text-[#333] rounded-[14px] rounded-tl-[4px]'
                    }`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      p: ({ node, ...props }) => <p className="mb-0" {...props} />,
                      ul: ({ node, ...props }) => <ul className="list-disc ml-4 mb-2" {...props} />,
                      ol: ({ node, ...props }) => <ol className="list-decimal ml-4 mb-2" {...props} />,
                      li: ({ node, ...props }) => <li className="mb-1" {...props} />,
                      table: ({ node, ...props }) => (
                        <div className="overflow-x-auto my-2">
                          <table
                            className="min-w-full border-collapse border border-gray-400 text-[11px]"
                            {...props}
                          />
                        </div>
                      ),
                      th: ({ node, ...props }) => (
                        <th className="border border-gray-400 px-2 py-1 bg-gray-200" {...props} />
                      ),
                      td: ({ node, ...props }) => (
                        <td className="border border-gray-400 px-2 py-1" {...props} />
                      ),
                    }}
                  >
                    {msg.text}
                  </ReactMarkdown>
                </div>
              </div>
            ))
          )}

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

        {/* Input Area */}
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
              className={`rounded-full p-[6px] transition-colors ${inputText.trim()
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
    </div>
  );
}
