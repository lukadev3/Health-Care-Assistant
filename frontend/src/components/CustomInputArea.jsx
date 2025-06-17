import React, {
  forwardRef,
  useRef,
  useEffect,
  useImperativeHandle,
  useCallback,
  useState
} from 'react';

const CustomInputArea = forwardRef((props, ref) => {
  const {
    value,
    onChange,
    onKeyDown,
    placeholder,
    visible = true,
    buttonLabel = "Send",
    onButtonClick,
    isLoading = false,
    autoFocus = false
  } = props;

  const divRef = useRef(null);
  const isComposing = useRef(false);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    if (divRef.current && value !== undefined && value !== divRef.current.textContent) {
      divRef.current.textContent = value;
    }
  }, [value]);

  useEffect(() => {
    if (autoFocus && divRef.current && visible) {
      divRef.current.focus();
    }
  }, [autoFocus, visible]);

  useImperativeHandle(ref, () => ({
    focus: () => divRef.current?.focus(),
    blur: () => divRef.current?.blur(),
    getBoundingClientRect: () => divRef.current?.getBoundingClientRect(),
    scrollIntoView: (options) => divRef.current?.scrollIntoView(options),
  }));

  const handleInput = useCallback(() => {
    if (!isComposing.current && onChange) {
      onChange({ target: { value: divRef.current?.textContent || '' } });
    }
  }, [onChange]);

  const handlePaste = useCallback((e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/plain');
    document.execCommand('insertText', false, text);
  }, []);

  const handleButtonClick = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (onButtonClick) {
      onButtonClick();
    }
  }, [onButtonClick]);

  const handleFocus = useCallback(() => {
    setIsFocused(true);
  }, []);

  const handleBlur = useCallback(() => {
    setIsFocused(false);
  }, []);

  return (
    <div style={{ 
      position: 'relative',
      width: '100%',
      opacity: visible ? 1 : 0,
      transform: visible ? 'translateY(0)' : 'translateY(10px)',
      transition: 'opacity 0.3s ease, transform 0.3s ease'
    }}>
      <div
        ref={divRef}
        contentEditable={!isLoading}
        onInput={handleInput}
        onKeyDown={(e) => {
          if (onKeyDown) onKeyDown(e);
          if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
            e.preventDefault();
            if (onButtonClick) onButtonClick();
          }
        }}
        onPaste={handlePaste}
        onCompositionStart={() => (isComposing.current = true)}
        onCompositionEnd={() => {
          isComposing.current = false;
          handleInput();
        }}
        onFocus={handleFocus}
        onBlur={handleBlur}
        suppressContentEditableWarning={true}
        placeholder={placeholder}
        data-placeholder={placeholder}
        style={{
          maxHeight: "200px",
          minHeight: "50px",
          padding: "12px 12px 12px 12px",
          backgroundColor: "#f7f7f7",
          fontSize: "15px",
          borderRadius: "15px",
          boxShadow: isFocused 
            ? "0 1px 4px rgba(0,0,0,0.3), 0 0 0 2px rgba(77, 77, 77, 0.25)" 
            : "0 1px 4px rgba(0,0,0,0.3)",
          outline: "none",
          overflowY: "auto",
          whiteSpace: "pre-wrap",
          transition: "all 0.3s ease",
        }}
      />
      
     <button
        onClick={handleButtonClick}
        disabled={isLoading}
        className={`custom-button ${isLoading ? 'disabled' : ''}`}
        >
        {isLoading ? (
        <div style={{
            width: '20px',
            height: '20px',
            border: '3px solid rgba(0, 0, 0, 0.1)',
            borderTop: '3px solid #555',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite'
        }} />
        ) : (
            buttonLabel
        )}
        </button>
    </div>
  );
});

export default CustomInputArea;