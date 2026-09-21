'use client';

import React, { useState, useRef, useEffect } from 'react';

// --- DATA STRUCTURES ---
interface EmailRecord { id: number; subject: string; sender: string; category: string; }
interface ShippingData { field: string; siValue: string; blValue: string; }
interface ReviewCase { id: number; relatedSubject: string; reason: string; status: string; }

// --- EXPANDED MOCK DATA ---
const mockInbox: EmailRecord[] = [
  { id: 1, subject: 'URGENT: Check Docs for Shipment 8829', sender: 'ops@globalshipping.com', category: 'Document Comparison' },
  { id: 2, subject: 'Invoice Question - September', sender: 'billing@techimports.com', category: 'Invoice Query' },
  { id: 3, subject: 'Draft BL attached for review', sender: 'agent@portlogistics.com', category: 'Document Comparison' },
  { id: 4, subject: 'Requesting new SI for Voyage 42', sender: 'client@exports.com', category: 'New SI Request' },
  { id: 5, subject: 'Office Hours for Public Holiday', sender: 'info@logistics.com', category: 'General Message' },
  { id: 6, subject: 'Earn $1000 working from home!', sender: 'scam@sketchy.com', category: 'Spam' },
  { id: 7, subject: 'Invoice 9920 Payment Confirmation', sender: 'finance@techimports.com', category: 'Invoice Query' },
  { id: 8, subject: 'BL Verification for Voyage 82', sender: 'agent@portlogistics.com', category: 'Document Comparison' },
  { id: 9, subject: 'Weekly operations update', sender: 'internal@averis.com', category: 'General Message' },
  { id: 10, subject: 'SI and BL attached for review', sender: 'ops@globalshipping.com', category: 'Document Comparison' },
  { id: 11, subject: 'Need help with new SI generation', sender: 'logistics@supplier.com', category: 'New SI Request' },
  { id: 12, subject: 'Final BL draft approval', sender: 'agent@portlogistics.com', category: 'Document Comparison' },
];

const mockComparisonData: ShippingData[] = [
  { field: 'Shipper', siValue: 'Global Exports Inc.', blValue: 'Global Exports Inc.' },
  { field: 'Consignee', siValue: 'Tech Imports LLC', blValue: 'Tech Imports LLC' },
  { field: 'Notify Party', siValue: 'Logistics Corp', blValue: 'Logistics Corp' },
  { field: 'Port of Loading', siValue: 'Shanghai', blValue: 'Shanghai' },
  { field: 'Port of Discharge', siValue: 'Los Angeles', blValue: 'Los Angeles' },
  { field: 'Container Count', siValue: '3', blValue: '4' }, 
  { field: 'Gross Weight (kg)', siValue: '22000', blValue: '22000' },
];

const mockQueue: ReviewCase[] = [
  { id: 101, relatedSubject: 'Fwd: Shipping Instructions - Voyage 42', reason: 'Unreadable PDF - Scanned image too blurry', status: 'Pending Review' },
  { id: 102, relatedSubject: 'Draft BL for Approval', reason: 'Missing required value: Port of Discharge', status: 'Pending Review' },
  { id: 103, relatedSubject: 'Check Docs for Shipment 8829', reason: 'Container Count missing from source SI', status: 'Pending Review' },
  { id: 104, relatedSubject: 'BL Verification for Voyage 82', reason: 'Consignee mismatch is ambiguous', status: 'Pending Review' },
  { id: 105, relatedSubject: 'SI and BL attached for review', reason: 'Failed to extract Gross Weight format', status: 'Pending Review' },
  { id: 106, relatedSubject: 'Final BL draft approval', reason: 'Port of Loading format unrecognized', status: 'Pending Review' },
];

const totalEmails = mockInbox.length;
const comparisonRequests = mockInbox.filter(email => email.category === 'Document Comparison').length;
const invoiceQueries = mockInbox.filter(email => email.category === 'Invoice Query').length;
const pendingReviews = mockQueue.length;

export default function Dashboard() {
  const [currentView, setCurrentView] = useState<'inbox' | 'queue'>('inbox');
  const [selectedEmail, setSelectedEmail] = useState<EmailRecord | null>(null);

  // --- DRAG TO RESIZE STATE ---
  const [sidebarWidth, setSidebarWidth] = useState(256); 
  const [isDragging, setIsDragging] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const isCollapsed = sidebarWidth < 160;

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !sidebarRef.current) return;
      const sidebarRect = sidebarRef.current.getBoundingClientRect();
      let newWidth = e.clientX - sidebarRect.left;

      if (newWidth < 88) newWidth = 88; 
      if (newWidth > 400) newWidth = 400; 

      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => setIsDragging(false);

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = 'none';
      document.body.style.cursor = 'grabbing';
    } else {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    };
  }, [isDragging]);

  const navigateTo = (view: 'inbox' | 'queue') => {
    setCurrentView(view);
    setSelectedEmail(null); 
  };

  // --- DYNAMIC LIST SENSOR LOGIC ---
  const listContainerRef = useRef<HTMLDivElement>(null);
  const [listWidth, setListWidth] = useState(1000);

  useEffect(() => {
    if (!listContainerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      setListWidth(entries[0].contentRect.width);
    });
    observer.observe(listContainerRef.current);
    return () => observer.disconnect();
  }, []);

  const hideCategory = listWidth < 820;
  const hideStatus = listWidth < 650;
  const stackQueue = listWidth < 600;

  return (
    <div 
      className="flex h-screen w-full items-center justify-center font-sans text-gray-800 bg-cover bg-center p-3 md:p-[5vh]"
      style={{ backgroundImage: "url('/background.jpg')" }}
    >
      <style>{`
        @keyframes stackIn { from { opacity: 0; transform: translateY(15px); } to { opacity: 1; transform: translateY(0); } }
        .animate-stack { opacity: 0; animation: stackIn 0.4s ease-out forwards; }
        @keyframes spinPop { 0% { transform: scale(0.3) rotate(-180deg); opacity: 0; } 70% { transform: scale(1.1) rotate(10deg); opacity: 1; } 100% { transform: scale(1) rotate(0deg); opacity: 1; } }
        .animate-spin-pop { animation: spinPop 0.6s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; }
        .scroll-container { scrollbar-width: auto; scrollbar-color: transparent transparent; transition: scrollbar-color 0.3s ease; }
        .scroll-container:hover { scrollbar-color: rgba(156, 163, 175, 0.6) transparent; }
        .scroll-container::-webkit-scrollbar { width: 14px; }
        .scroll-container::-webkit-scrollbar-track { background: transparent; }
        .scroll-container::-webkit-scrollbar-thumb { background-color: transparent; border-radius: 14px; border: 4px solid transparent; background-clip: padding-box; }
        .scroll-container:hover::-webkit-scrollbar-thumb { background-color: rgba(156, 163, 175, 0.8); }
      `}</style>

      {/* --- MAIN BACKDROP CARD --- */}
      <div className="flex flex-col md:flex-row w-full h-full bg-white/50 backdrop-blur-2xl rounded-2xl md:rounded-3xl shadow-2xl border border-white/50 overflow-hidden relative">
        
        {/* --- FLOATING SIDEBAR / BOTTOM BAR --- */}
        <div 
          ref={sidebarRef}
          style={{ '--desktop-width': `${sidebarWidth}px` } as React.CSSProperties}
          className="order-2 md:order-1 relative shrink-0 flex flex-row md:flex-col bg-white/90 shadow-[0_-4px_24px_rgba(0,0,0,0.06)] md:shadow-[4px_0_24px_rgba(0,0,0,0.06)] border border-white/80 z-30 m-3 mt-1.5 mb-3 md:m-4 md:mr-1 rounded-2xl transition-shadow w-auto md:w-[var(--desktop-width)]"
        >
          {/* DRAG HANDLE (HIDDEN ON MOBILE) */}
          <div className="hidden md:flex absolute top-0 right-0 w-8 h-full translate-x-1/2 z-50 items-center justify-center group/handle">
            <div 
              onMouseDown={() => setIsDragging(true)}
              className={`flex items-center justify-center w-6 h-12 bg-white shadow-md border border-gray-200 rounded-full transition-all duration-200 cursor-grab ${isDragging ? 'opacity-100 bg-blue-50 scale-100 cursor-grabbing' : 'opacity-0 scale-90 group-hover/handle:opacity-100 group-hover/handle:scale-100'}`}
            >
              <svg className="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 16l-4-4 4-4" />
                <path d="M14 16l4-4-4-4" />
              </svg>
            </div>
          </div>

          {/* LOGO HEADER */}
          <div className={`hidden md:flex items-center border-b border-gray-100 min-h-[5.5rem] overflow-hidden ${isCollapsed ? 'p-4 justify-center' : 'p-5 justify-start'}`}>
            {isCollapsed ? (
              <div className="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center text-orange-600 font-extrabold text-xl shrink-0 mx-auto">
                S
              </div>
            ) : (
              <h2 className="text-xl font-extrabold text-orange-500 tracking-tight leading-tight truncate w-full">
                ShipCheck<br /><span className="text-gray-900">Dashboard</span>
              </h2>
            )}
          </div>
          
          {/* NAVIGATION BUTTONS */}
          <nav className="flex-1 p-2 md:p-4 flex flex-row md:flex-col justify-around md:justify-start space-y-0 md:space-y-2">
            
            <button 
              onClick={() => navigateTo('inbox')}
              /* UI TWEAK: Strict !w-12 !h-12 enforces the square dimension over all other flex utilities when collapsed[cite: 9] */
              className={`group flex items-center transition-all duration-200 shrink-0
                flex-1 flex-col w-full py-2 justify-center rounded-lg gap-1
                md:flex-none md:flex-row md:gap-3
                ${isCollapsed ? 'md:!w-12 md:!h-12 md:p-0 md:justify-center md:rounded-xl md:mx-auto' : 'md:!w-full md:!h-auto md:px-4 md:py-3 md:justify-start md:rounded-lg'}
                ${currentView === 'inbox' && !selectedEmail ? 'bg-blue-50 text-blue-700 shadow-sm' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              <div className="relative shrink-0 flex items-center justify-center w-5 h-5">
                <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>
                  <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>
                </svg>
              </div>
              <span className={`text-[10px] md:text-sm truncate ${isCollapsed ? 'md:hidden' : ''}`}>Email Inbox</span>
            </button>
            
            <button 
              onClick={() => navigateTo('queue')}
              /* UI TWEAK: Strict !w-12 !h-12 applied here as well to match the Inbox and Logo perfectly[cite: 9] */
              className={`group flex items-center transition-all duration-200 shrink-0
                flex-1 flex-col w-full py-2 justify-center rounded-lg gap-1
                md:flex-none md:flex-row md:gap-3
                ${isCollapsed ? 'md:!w-12 md:!h-12 md:p-0 md:justify-center md:rounded-xl md:mx-auto' : 'md:!w-full md:!h-auto md:px-4 md:py-3 md:justify-between md:rounded-lg'}
                ${currentView === 'queue' ? 'bg-orange-50 text-orange-700 shadow-sm' : 'text-gray-600 hover:bg-gray-50'}`}
            >
              <div className={`flex flex-col md:flex-row items-center gap-1 md:gap-3 min-w-0 ${isCollapsed ? 'md:justify-center' : 'md:justify-start'}`}>
                <div className="relative shrink-0 flex items-center justify-center w-5 h-5">
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>
                  </svg>
                  
                  {(isCollapsed || pendingReviews > 0) && (
                    <span className={`absolute -top-1.5 -right-2 w-[16px] h-[16px] bg-red-500 text-white text-[9px] font-bold flex items-center justify-center rounded-full shadow-sm border border-white ${isCollapsed ? '' : 'md:hidden'}`}>
                      {pendingReviews}
                    </span>
                  )}
                </div>
                
                <span className={`text-[10px] md:text-sm truncate ${isCollapsed ? 'md:hidden' : ''}`}>Human Review</span>
              </div>
              
              {!isCollapsed && (
                <span className="hidden md:inline-flex shrink-0 ml-auto bg-orange-200 text-orange-800 text-xs px-2 py-1 rounded-full">
                  {pendingReviews}
                </span>
              )}
            </button>
          </nav>
        </div>

        {/* --- MAIN CONTENT AREA --- */}
        <div className="order-1 md:order-2 flex-1 flex flex-col min-w-0 relative pt-3 px-3 pb-1.5 md:py-4 md:pr-4 md:pl-3">
          
          {/* LAYER 1: ANALYTICS HEADER */}
          <div className="shrink-0 pb-3 md:pb-5 z-20">
            <h2 className="text-xs md:text-sm font-bold text-gray-500 tracking-widest uppercase mb-1">Getting Started</h2>
            
            <h1 className="text-xl md:text-2xl font-bold text-gray-900 mb-4 md:mb-5 flex items-center gap-2">
              System Analytics Overview 
              <svg className="w-6 h-6 text-gray-900 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"></path>
                <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"></path>
                <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"></path>
                <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"></path>
              </svg>
            </h1>
            
            <div className="flex flex-col lg:flex-row gap-3 md:gap-4">
              <div className="flex-1 bg-white/80 p-3 md:p-4 rounded-2xl shadow-sm border border-green-200/50 flex items-center gap-4 backdrop-blur-md">
                <div className="relative w-10 h-10 md:w-12 md:h-12 shrink-0 flex items-center justify-center animate-spin-pop">
                  <div className="absolute inset-0 bg-green-100 rounded-xl rotate-0"></div>
                  <div className="absolute inset-0 bg-green-100 rounded-xl rotate-45"></div>
                  <svg className="relative z-10 w-5 h-5 md:w-6 md:h-6 text-green-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                  </svg>
                </div>
                <div>
                  <p className="text-lg md:text-xl font-bold text-gray-800">{totalEmails}</p>
                  <p className="text-xs md:text-sm text-gray-500">Emails Processed</p>
                </div>
              </div>

              <div className="flex-1 bg-white/80 p-3 md:p-4 rounded-2xl shadow-sm border border-blue-200/50 flex items-center gap-4 backdrop-blur-md">
                <div className="relative w-10 h-10 md:w-12 md:h-12 shrink-0 flex items-center justify-center animate-spin-pop" style={{ animationDelay: '100ms' }}>
                  <div className="absolute inset-0 bg-blue-100 rounded-xl rotate-0"></div>
                  <div className="absolute inset-0 bg-blue-100 rounded-xl rotate-45"></div>
                  <svg className="relative z-10 w-5 h-5 md:w-6 md:h-6 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <polyline points="10 9 9 9 8 9"></polyline>
                  </svg>
                </div>
                <div>
                  <p className="text-lg md:text-xl font-bold text-gray-800">{comparisonRequests}</p>
                  <p className="text-xs md:text-sm text-gray-500">Document Checks</p>
                </div>
              </div>

              <div className="flex-1 bg-white/80 p-3 md:p-4 rounded-2xl shadow-sm border border-gray-200/50 flex items-center gap-4 backdrop-blur-md">
                <div className="relative w-10 h-10 md:w-12 md:h-12 shrink-0 flex items-center justify-center animate-spin-pop" style={{ animationDelay: '200ms' }}>
                  <div className="absolute inset-0 bg-gray-200 rounded-xl rotate-0"></div>
                  <div className="absolute inset-0 bg-gray-200 rounded-xl rotate-45"></div>
                  <svg className="relative z-10 w-5 h-5 md:w-6 md:h-6 text-gray-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="1" x2="12" y2="23"></line>
                    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
                  </svg>
                </div>
                <div>
                  <p className="text-lg md:text-xl font-bold text-gray-800">{invoiceQueries}</p>
                  <p className="text-xs md:text-sm text-gray-500">Invoice Queries</p>
                </div>
              </div>
            </div>
          </div>

          {/* LAYER 2: THE NEW LIST CARD WRAPPER */}
          <div className="flex-1 flex flex-col min-w-0 relative">
            
            <div className="flex-1 flex flex-col bg-white/70 backdrop-blur-xl shadow-xl border border-white/80 rounded-2xl overflow-hidden relative">
              
              {/* STATIC CARD HEADER */}
              <div className="shrink-0 px-4 md:px-8 pt-4 md:pt-6 pb-3 border-b border-gray-200/50 flex justify-between items-end z-10 bg-white/40">
                <h2 className="text-xl md:text-2xl font-bold text-gray-800 tracking-tight">
                  {currentView === 'inbox' && !selectedEmail && 'Processing Inbox'}
                  {selectedEmail && 'Discrepancy Report'}
                  {currentView === 'queue' && 'Pending Resolutions'}
                </h2>
                
                {selectedEmail && (
                  <button 
                    onClick={() => setSelectedEmail(null)}
                    className="text-blue-600 hover:text-blue-800 text-sm md:text-base font-semibold flex items-center gap-2 transition-colors active:scale-95 whitespace-nowrap"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline>
                    </svg>
                    Back
                  </button>
                )}
              </div>

              {/* FADING SCROLLABLE LIST AREA */}
              <div 
                className="flex-1 relative min-h-0"
                style={{ 
                  WebkitMaskImage: 'linear-gradient(to bottom, black 80%, transparent 100%)',
                  maskImage: 'linear-gradient(to bottom, black 80%, transparent 100%)' 
                }}
              >
                <div ref={listContainerRef} className="absolute inset-0 overflow-y-auto overflow-x-hidden scroll-container px-4 md:px-8 pb-8">
                  
                  {/* VIEW 1: THE INBOX */}
                  {currentView === 'inbox' && !selectedEmail && (
                    <table className="w-full text-left border-collapse table-fixed mt-2">
                      <thead>
                        <tr className="border-b border-gray-200 text-gray-500 text-xs md:text-sm uppercase tracking-wider">
                          <th className="py-4 px-1 md:px-2 font-semibold truncate">Sender</th>
                          <th className="py-4 px-1 md:px-2 font-semibold w-2/5 truncate">Subject</th>
                          {!hideCategory && (
                            <th className="py-4 px-2 font-semibold truncate">Category</th>
                          )}
                          <th className="py-4 px-1 md:px-2 font-semibold w-28 md:w-36 whitespace-nowrap text-right md:text-left">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {mockInbox.map((email, index) => (
                          <tr 
                            key={email.id} 
                            className="border-b border-gray-100 hover:bg-white/60 transition-colors animate-stack text-sm md:text-base"
                            style={{ animationDelay: `${index * 50}ms` }}
                          >
                            <td className="py-4 px-1 md:px-2 text-gray-600 truncate" title={email.sender}>{email.sender}</td>
                            <td className="py-4 px-1 md:px-2 font-semibold text-gray-800 truncate" title={email.subject}>{email.subject}</td>
                            
                            {!hideCategory && (
                              <td className="py-4 px-2">
                                <span className={`h-8 md:h-10 px-3 md:px-4 inline-flex items-center justify-center rounded-full text-xs md:text-sm font-bold tracking-wide shadow-sm whitespace-nowrap shrink-0 max-w-fit
                                  ${email.category === 'Document Comparison' ? 'bg-blue-100 text-blue-800' : 
                                    email.category === 'Spam' ? 'bg-red-100 text-red-800' : 
                                    email.category === 'New SI Request' ? 'bg-purple-100 text-purple-800' : 
                                    'bg-gray-200 text-gray-800'}`}
                                >
                                  {email.category}
                                </span>
                              </td>
                            )}
                            
                            <td className="py-4 px-1 md:px-2 flex justify-end md:justify-start">
                              {email.category === 'Document Comparison' ? (
                                <button 
                                  onClick={() => setSelectedEmail(email)}
                                  className="h-8 md:h-10 w-full md:w-auto bg-blue-600 text-white px-3 md:px-4 rounded-lg text-xs md:text-sm font-medium hover:bg-blue-700 shadow-md transition-all active:scale-95 inline-flex items-center justify-center gap-2 whitespace-nowrap shrink-0"
                                >
                                  Review Docs
                                </button>
                              ) : (
                                <span className="h-8 md:h-10 inline-flex items-center text-gray-400 text-xs md:text-sm italic whitespace-nowrap">Ignored</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}

                  {/* VIEW 2: SI VS BL REPORT */}
                  {selectedEmail && (
                    <table className="w-full text-left border-collapse table-fixed mt-2">
                      <thead>
                        <tr className="border-b border-gray-200 text-gray-500 text-xs md:text-sm uppercase tracking-wider">
                          <th className="py-4 px-1 md:px-2 font-semibold w-1/4 truncate">Field</th>
                          <th className="py-4 px-1 md:px-2 font-semibold w-1/3 text-blue-900 truncate">SI</th>
                          <th className="py-4 px-1 md:px-2 font-semibold w-1/3 text-purple-900 truncate">Draft BL</th>
                          {!hideStatus && (
                            <th className="py-4 px-2 font-semibold w-32 md:w-40 truncate">Status</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {mockComparisonData.map((row, index) => {
                          const isMismatch = row.siValue !== row.blValue;
                          
                          let rowClasses = "border-b border-gray-100 transition-colors animate-stack text-sm md:text-base ";
                          if (hideStatus) {
                            rowClasses += isMismatch 
                              ? "bg-red-50/80 hover:bg-red-100/80 " 
                              : "bg-green-50/80 hover:bg-green-100/80 ";
                          } else {
                            rowClasses += "hover:bg-white/60 ";
                          }

                          return (
                            <tr 
                              key={index} 
                              className={rowClasses}
                              style={{ animationDelay: `${index * 50}ms` }}
                            >
                              <td className="py-4 px-1 md:px-2 font-medium text-gray-700 truncate">{row.field}</td>
                              <td className="py-4 px-1 md:px-2 truncate">{row.siValue}</td>
                              <td className={`py-4 px-1 md:px-2 truncate ${isMismatch && !hideStatus ? 'text-red-600 font-bold' : ''}`}>
                                {row.blValue}
                              </td>
                              
                              {!hideStatus && (
                                <td className="py-4 px-2">
                                  {isMismatch ? (
                                    <span className="h-8 md:h-10 px-3 md:px-4 inline-flex items-center justify-center bg-red-100 text-red-800 rounded-full text-[10px] md:text-xs font-bold shadow-sm whitespace-nowrap shrink-0">Mismatch Detected</span>
                                  ) : (
                                    <span className="h-8 md:h-10 px-3 md:px-4 inline-flex items-center justify-center bg-green-100 text-green-800 rounded-full text-[10px] md:text-xs font-bold shadow-sm whitespace-nowrap shrink-0">Verified Match</span>
                                  )}
                                </td>
                              )}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}

                  {/* VIEW 3: HUMAN REVIEW QUEUE */}
                  {currentView === 'queue' && (
                    <div className="grid gap-3 md:gap-4 mt-4">
                      {mockQueue.map((item, index) => (
                        <div 
                          key={item.id} 
                          className={`bg-white/80 p-4 md:p-6 rounded-xl shadow-sm border-l-4 border-orange-500 flex hover:shadow-md transition-all animate-stack backdrop-blur-md gap-3 md:gap-4 ${stackQueue ? 'flex-col' : 'flex-col md:flex-row md:justify-between md:items-center'}`}
                          style={{ animationDelay: `${index * 50}ms` }}
                        >
                          <div className="min-w-0 flex-1">
                            <h3 className="font-bold text-base md:text-lg text-gray-800 mb-1.5 leading-snug">{item.relatedSubject}</h3>
                            <p className="text-orange-700 font-medium text-xs md:text-sm flex items-start gap-2 leading-snug">
                              <svg className="w-4 h-4 shrink-0 mt-[2px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                                <line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line>
                              </svg>
                              <span>{item.reason}</span>
                            </p>
                          </div>
                          <div className={`shrink-0 flex justify-end ${stackQueue ? 'mt-1' : ''}`}>
                            <button className="h-8 md:h-10 px-3 md:px-4 inline-flex items-center justify-center bg-orange-100 text-orange-800 rounded-lg text-xs md:text-sm font-bold shadow-sm hover:bg-orange-200 hover:shadow transition-all active:scale-95 whitespace-nowrap">
                              Resolve Case
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  <div className="h-24 w-full shrink-0"></div>
                  
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>
    </div>
  );
}