import { useRef, useEffect, useState } from "react";

export function EditableTextArea({
  value,
  onChange,
  onKeyDown,
  autoFocus = false,
  placeholder = "Type your message..."
}) {
  const divRef = useRef(null);
  const isComposing = useRef(false);
  const lastHtml = useRef("");
  const lastSelection = useRef({ start: 0, end: 0 });
  const didInitialFocus = useRef(false); 
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(true); 
  }, []);

  const saveSelection = () => {
    if (!divRef.current || isComposing.current) return;

    const selection = window.getSelection();
    if (selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);
    const preCaretRange = range.cloneRange();
    preCaretRange.selectNodeContents(divRef.current);
    preCaretRange.setEnd(range.endContainer, range.endOffset);

    const length = preCaretRange.toString().length;

    lastSelection.current = {
      start: length,
      end: length
    };
    lastHtml.current = divRef.current.innerHTML;
  };

  const restoreSelection = () => {
    if (!divRef.current || !lastHtml.current) return;

    const selection = window.getSelection();
    selection.removeAllRanges();

    const range = document.createRange();
    let charIndex = 0;
    let nodeStack = [divRef.current];
    let node;
    let foundStart = false;
    let stop = false;

    while (!stop && (node = nodeStack.pop())) {
      if (node.nodeType === Node.TEXT_NODE) {
        const nextCharIndex = charIndex + node.length;
        if (
          !foundStart &&
          lastSelection.current.start >= charIndex &&
          lastSelection.current.start <= nextCharIndex
        ) {
          range.setStart(node, lastSelection.current.start - charIndex);
          foundStart = true;
        }
        if (
          foundStart &&
          lastSelection.current.end >= charIndex &&
          lastSelection.current.end <= nextCharIndex
        ) {
          range.setEnd(node, lastSelection.current.end - charIndex);
          stop = true;
        }
        charIndex = nextCharIndex;
      } else {
        let i = node.childNodes.length;
        while (i--) {
          nodeStack.push(node.childNodes[i]);
        }
      }
    }

    selection.addRange(range);
  };

  const setCaretToEnd = (element) => {
    const range = document.createRange();
    const selection = window.getSelection();
    range.selectNodeContents(element);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  };

  useEffect(() => {
    if (!divRef.current) return;

    if (divRef.current.innerHTML !== value) {
      saveSelection();
      divRef.current.innerHTML = value || "";
      lastHtml.current = divRef.current.innerHTML;

      if (autoFocus && !didInitialFocus.current) {
        divRef.current.focus();
        setCaretToEnd(divRef.current);
        didInitialFocus.current = true;
        return;
      }

      restoreSelection();
    }

    if (autoFocus && !didInitialFocus.current) {
      divRef.current.focus();
      setCaretToEnd(divRef.current);
      didInitialFocus.current = true;
    }
  }, [value, autoFocus]);

  const handleInput = () => {
    if (!divRef.current || isComposing.current) return;

    saveSelection();

    if (onChange) {
      onChange({ target: { value: divRef.current.innerHTML } });
    }
  };

  const handleKeyDown = (e) => {
    saveSelection();
    if (onKeyDown) onKeyDown(e);
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const text = e.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
  };

  const handleCompositionStart = () => {
    isComposing.current = true;
  };

  const handleCompositionEnd = () => {
    isComposing.current = false;
    saveSelection();
  };

  return (
    <div
      ref={divRef}
      contentEditable
      onInput={handleInput}
      onKeyDown={handleKeyDown}
      onPaste={handlePaste}
      onBlur={saveSelection}
      onFocus={restoreSelection}
      onCompositionStart={handleCompositionStart}
      onCompositionEnd={handleCompositionEnd}
      suppressContentEditableWarning={true}
      data-placeholder={placeholder}
      style={{
        minWidth: "30em",
        minHeight: "100px",
        maxWidth: "500px",
        maxHeight: "10em",
        padding: "0.3em 0.5em",
        backgroundColor: "white",
        fontSize: "15px",
        textAlign: "left",
        borderRadius: "5px",
        overflowY: "auto",
        whiteSpace: "pre-wrap",
        border: "1px solid #ccc",
        boxShadow: "0 4px 8px 0 rgba(0, 0, 0, 0.05), 0 6px 20px 0 rgba(0, 0, 0, 0.05)",
        outline: "none",
        position: "relative",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(10px)",
        transition: "opacity 0.3s ease, transform 0.3s ease"
      }}
    />
  );
}
