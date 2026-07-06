import { useState, useRef, useEffect } from "react";


export default function Chat() {
    const [messages, setMessages] = useState([
        {
            id: 1,
            from: "bot",
            text: "Hello! How can I help you today?",
        },
    ]);

    const [input, setInput] = useState("");
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({
            behavior: "smooth",
        });
    }, [messages]);
    useEffect(() => {
        const textarea = textareaRef.current;
        if (!textarea) return;

        textarea.style.height = "auto";

        const maxHeight = 160;

        if (textarea.scrollHeight > maxHeight) {
            textarea.style.height = `${maxHeight}px`;
            textarea.style.overflowY = "auto";
        } else {
            textarea.style.height = `${textarea.scrollHeight}px`;
            textarea.style.overflowY = "hidden";
        }
    }, [input]);
    const handleChange = (e) => {
        setInput(e.target.value);
    };

    function send() {
        if (!input.trim()) return;

        const userMsg = {
            id: Date.now(),
            from: "user",
            text: input.trim(),
        };

        setMessages((prev) => [...prev, userMsg]);
        setInput("");

        requestAnimationFrame(() => {
            if (textareaRef.current) {
                textareaRef.current.style.height = "auto";
                textareaRef.current.style.overflowY = "hidden";
            }
        });
        setTimeout(() => {
            setMessages((prev) => [
                ...prev,
                {
                    id: Date.now() + 1,
                    from: "bot",
                    text: `I'm a simple demo bot. You said: "${userMsg.text}"`,
                },
            ]);
        }, 700);
    }
    function onKeyDown(e) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
        }
    }

    return (
        <div className="flex flex-col h-full w-full  rounded-2xl overflow-hidden shadow-xl border border-gray-700 bg-gray-800">
            {/* Header */}
            <div className="px-4 py-3 bg-gray-900 text-white flex items-center justify-between border-b border-gray-700">
                <h2 className="font-semibold text-base">Documind Chatbot</h2>
                <span className="text-xs text-green-400">● Online</span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-4 py-3 scrollbar-thumb-cyan-600 space-y-3">
                {messages.map((m) => (
                    <div
                        key={m.id}
                        className={`flex ${m.from === "user" ? "justify-end" : "justify-start"
                            }`}
                    >
                        <div
                            className={`max-w-[75%] px-3 py-2 rounded-2xl ${m.from === "user"
                                ? "bg-blue-600 text-white rounded-br-sm"
                                : "bg-gray-700 text-gray-100 rounded-bl-sm"
                                }`}
                        >
                            {m.text}
                        </div>
                    </div>
                ))}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="border-t border-gray-700 bg-gray-900 p-3">
                <div className="flex items-end gap-2 rounded-2xl border border-gray-700 bg-gray-800 px-3 py-2">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={handleChange}
                        onKeyDown={onKeyDown}
                        rows={1}
                        placeholder="Send a message..."
                        className="flex-1 min-h-5 max-h-32 resize-none overflow-y-auto bg-transparent text-white placeholder-gray-400 outline-none leading-6 py-1 scrollbar-none"
                    />
                    <button
                        onClick={send}
                        className="bg-blue-600 hover:bg-blue-700 transition-colors text-white px-4 py-2 rounded-lg text-sm"
                    >
                        Send
                    </button>
                </div>
            </div>
        </div>
    );
}