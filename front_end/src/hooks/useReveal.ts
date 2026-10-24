import { useEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

export function useReveal<T extends HTMLElement>(): [
  RefObject<T | null>,
  boolean,
] {
  const elementRef = useRef<T | null>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const element = elementRef.current
    if (!element) {
      return
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.15 },
    )

    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [elementRef, isVisible]
}
