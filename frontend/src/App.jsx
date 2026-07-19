import React, { useState } from 'react';

// Static configuration matching your FastAPI network setup
const API_BASE = "http://127.0.0.1:8000";

export default function App() {
  const [query, setQuery] = useState("");
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  // Pagination Tracking to prevent massive e-ink scrolling loops
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 5;

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setStatusMessage("[ Searching catalog... ]");
    setBooks([]);
    setCurrentPage(1);

    try {
      const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}&type=title`);
      if (!res.ok) throw new Error("Search endpoint returned an error status.");
      const data = await res.json();
      setBooks(data);
      setStatusMessage(data.length === 0 ? "No results found." : "");
    } catch (err) {
      setStatusMessage(`[ Search Error: ${err.message} ]`);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async (book) => {
    // Immediate, non-animated state feedback for e-ink responsiveness
    setStatusMessage(`[ Sending "${book.title}"... ]`);

    try {
      const res = await fetch(`${API_BASE}/api/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: book.id,
          mirrorUrl: book.mirror_url,
          md5: book.md5,
          title: book.title,
          convert: true // Automatically passes the Amazon text conversion rule
        })
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setStatusMessage(`✅ SUCCESS: "${book.title}" sent to Kindle!`);
      } else {
        setStatusMessage(`❌ FAILED: ${data.error || "Transmission rejected."}`);
      }
    } catch (err) {
      setStatusMessage(`❌ SYSTEM ERROR: ${err.message}`);
    }
  };

  // Safe client-side pagination splits
  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentBooks = books.slice(indexOfFirstItem, indexOfLastItem);
  const totalPages = Math.ceil(books.length / itemsPerPage);

  return (
    <div style={styles.container}>
      {/* HEADER BAR */}
      <h1 style={styles.title}>KIBGE DELIVERY GATEWAY</h1>

      {/* SEARCH INTERFACE CONTAINER */}
      <form onSubmit={handleSearch} style={styles.searchForm}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter book title..."
          style={styles.input}
          disabled={loading}
        />
        <button type="submit" style={styles.button} disabled={loading}>
          {loading ? "WAIT" : "SEARCH"}
        </button>
      </form>

      {/* SYSTEM STATUS FEEDBACK (Static Text Only) */}
      {statusMessage && (
        <div style={styles.statusBar}>
          <strong>{statusMessage}</strong>
        </div>
      )}

      {/* BOOK CATALOG MATRIX GRID */}
      <div style={styles.catalogList}>
        {currentBooks.map((book) => (
          <div key={book.id} style={styles.bookCard}>
            <table style={styles.tableLayout}>
              <tbody>
                <tr>
                  {/* Optional Proxy Image Slot (Rendered cleanly without modern styling tricks) */}
                  {book.cover_url && (
                    <td style={styles.coverCell}>
                      <img
                        src={`${API_BASE}/api/proxy-cover?url=${encodeURIComponent(book.cover_url)}`}
                        alt=""
                        style={styles.coverImg}
                        fallback="none"
                      />
                    </td>
                  )}
                  <td style={styles.metaCell}>
                    <div style={styles.bookTitle}>{book.title}</div>
                    <div style={styles.bookMeta}>By: {book.author}</div>
                    <div style={styles.bookMeta}>
                      Year: {book.year} | Format: {book.extension.toUpperCase()} | Size: {book.size}
                    </div>

                    {/* TRIGGER BUTTON SETUP WITH SOLID HIGHLIGHT HITBOXES */}
                    <button
                      onClick={() => handleSend(book)}
                      style={styles.sendButton}
                    >
                      DELIVER TO DEVICE →
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* PAGINATION PANEL */}
      {totalPages > 1 && (
        <div style={styles.paginationRow}>
          <button
            onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
            disabled={currentPage === 1}
            style={styles.navButton}
          >
            « PREV PAGE
          </button>
          <span style={styles.pageLabel}>
            PAGE {currentPage} OF {totalPages}
          </span>
          <button
            onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
            disabled={currentPage === totalPages}
            style={styles.navButton}
          >
            NEXT PAGE »
          </button>
        </div>
      )}
    </div>
  );
}

// --- E-INK COMPATIBLE INLINE CORE STYLES ---
// Completely avoiding runtime computing libraries like styled-components or Tailwind
const styles = {
  container: {
    fontFamily: 'monospace, Courier, sans-serif',
    backgroundColor: '#FFFFFF',
    color: '#000000',
    padding: '15px',
    maxWidth: '800px',
    margin: '0 auto',
  },
  title: {
    fontSize: '22px',
    textAlign: 'center',
    borderBottom: '4px solid #000000',
    paddingBottom: '8px',
    letterSpacing: '1px',
    margin: '10px 0 20px 0',
  },
  searchForm: {
    display: 'flex',
    marginBottom: '15px',
  },
  input: {
    flex: 1,
    border: '2px solid #000000',
    padding: '12px',
    fontSize: '16px',
    backgroundColor: '#FFFFFF',
    color: '#000000',
    borderRadius: '0px', // Explicitly square flat layouts render best on old webkit
  },
  button: {
    border: '2px solid #000000',
    borderLeft: 'none',
    backgroundColor: '#000000',
    color: '#FFFFFF',
    padding: '0 20px',
    fontSize: '16px',
    fontWeight: 'bold',
    cursor: 'pointer',
    borderRadius: '0px',
  },
  statusBar: {
    border: '2px dashed #000000',
    padding: '10px',
    textAlign: 'center',
    marginBottom: '15px',
    fontSize: '14px',
    backgroundColor: '#FFFFFF',
  },
  catalogList: {
    marginTop: '10px',
  },
  bookCard: {
    border: '2px solid #000000',
    padding: '12px',
    marginBottom: '15px',
    backgroundColor: '#FFFFFF',
  },
  tableLayout: {
    width: '100%',
    borderCollapse: 'collapse',
  },
  coverCell: {
    width: '70px',
    verticalAlign: 'top',
    paddingRight: '12px',
  },
  coverImg: {
    width: '65px',
    height: 'auto',
    border: '1px solid #000000',
    display: 'block',
  },
  metaCell: {
    verticalAlign: 'top',
  },
  bookTitle: {
    fontSize: '16px',
    fontWeight: 'bold',
    textTransform: 'uppercase',
    marginBottom: '4px',
  },
  bookMeta: {
    fontSize: '13px',
    marginBottom: '4px',
    lineHeight: '1.4',
  },
  sendButton: {
    marginTop: '8px',
    display: 'block',
    width: '100%',
    backgroundColor: '#FFFFFF',
    color: '#000000',
    border: '2px solid #000000',
    padding: '10px',
    fontSize: '14px',
    fontWeight: 'bold',
    textAlign: 'center',
    cursor: 'pointer',
    borderRadius: '0px',
  },
  paginationRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: '20px',
    borderTop: '2px solid #000000',
    paddingTop: '15px',
  },
  navButton: {
    border: '2px solid #000000',
    backgroundColor: '#FFFFFF',
    color: '#000000',
    padding: '10px 15px',
    fontSize: '14px',
    fontWeight: 'bold',
    cursor: 'pointer',
    borderRadius: '0px',
  },
  pageLabel: {
    fontSize: '14px',
    fontWeight: 'bold',
  }
};